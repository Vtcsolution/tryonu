"""My looks: every finished try-on of a member, for the Gallery page; and
"this one came out wrong", which an admin answers in Admin → Try-ons."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.logging import logger
from app.core.rate_limit import rate_limiter
from app.models.developer import DeveloperTryOn
from app.models.enums import JobStatus
from app.models.outfit import Outfit
from app.models.tryon import TryOnJob
from app.models.tryon_report import TryOnReport
from app.services import credit_service

router = APIRouter(prefix="/tryon", tags=["tryon"])
admin_router = APIRouter(prefix="/admin/tryon-reports", tags=["admin"])

REASONS = ("wrong_product", "merged", "extra_item", "not_me", "bad_quality", "other")


class GalleryItemOut(BaseModel):
    job_id: str
    image_url: str
    width: int | None
    height: int | None
    what: str
    created_at: datetime


class GalleryOut(BaseModel):
    items: list[GalleryItemOut]
    total: int
    next_offset: int | None


def _what(job: TryOnJob) -> str:
    if job.outfit is not None:
        return f"Outfit · {len(job.outfit.items)} pieces"
    return job.product.name[:140] if job.product is not None else "Your own item"


@router.get("/gallery", response_model=GalleryOut)
async def gallery(me: CurrentUser, db: DbSession, offset: int = Query(default=0, ge=0), limit: int = Query(default=24, ge=1, le=60)):
    """Every finished try-on, newest first, a page at a time: hundreds stay fast."""
    base = select(TryOnJob).where(
        TryOnJob.user_id == me.id,
        TryOnJob.status == JobStatus.COMPLETED,
        TryOnJob.id.notin_(select(DeveloperTryOn.tryon_job_id)),  # not try-ons made for API customers
    )
    total = int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    jobs = (
        await db.execute(
            base.options(
                selectinload(TryOnJob.result),
                selectinload(TryOnJob.product),
                selectinload(TryOnJob.outfit).selectinload(Outfit.items),
            )
            .order_by(TryOnJob.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    items = [
        GalleryItemOut(
            job_id=j.id, image_url=j.result.image_url, width=j.result.width, height=j.result.height,
            what=_what(j), created_at=j.created_at,
        )
        for j in jobs
        if j.result is not None
    ]
    return GalleryOut(items=items, total=total, next_offset=offset + limit if offset + limit < total else None)


class ReportIn(BaseModel):
    reason: str = Field(pattern="^(" + "|".join(REASONS) + ")$")
    note: str | None = Field(default=None, max_length=1000)


class ReportOut(BaseModel):
    status: str
    reason: str


@router.post(
    "/{job_id}/report",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("tryon_report", limit=30, window_seconds=3600))],
)
async def report_tryon(job_id: str, payload: ReportIn, me: CurrentUser, db: DbSession):
    job = await db.get(TryOnJob, job_id)
    if job is None or job.user_id != me.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a finished try-on can be reported.")
    if await db.scalar(select(TryOnReport.id).where(TryOnReport.job_id == job_id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You've already reported this try-on. We're looking at it.")
    db.add(TryOnReport(job_id=job_id, user_id=me.id, reason=payload.reason, note=(payload.note or "").strip() or None))
    await db.commit()
    return ReportOut(status="open", reason=payload.reason)


class AdminReportOut(BaseModel):
    id: str
    job_id: str
    user_email: str | None
    reason: str
    note: str | None
    status: str
    credit_cost: int
    credits_refunded: int
    image_url: str | None
    what: str
    created_at: datetime


def _report_out(r: TryOnReport) -> AdminReportOut:
    job = r.job
    return AdminReportOut(
        id=r.id, job_id=r.job_id, user_email=r.user.email if r.user else None, reason=r.reason, note=r.note,
        status=r.status, credit_cost=job.credit_cost, credits_refunded=r.credits_refunded,
        image_url=job.result.image_url if job.result else None, what=_what(job), created_at=r.created_at,
    )


_REPORT_LOAD = (
    selectinload(TryOnReport.user),
    selectinload(TryOnReport.job).selectinload(TryOnJob.result),
    selectinload(TryOnReport.job).selectinload(TryOnJob.product),
    selectinload(TryOnReport.job).selectinload(TryOnJob.outfit).selectinload(Outfit.items),
)


async def _report(db: DbSession, report_id: str) -> TryOnReport:
    r = await db.scalar(select(TryOnReport).where(TryOnReport.id == report_id).options(*_REPORT_LOAD))
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return r


@admin_router.get("", response_model=list[AdminReportOut])
async def list_reports(_: AdminUser, db: DbSession, show: str = Query(default="open", pattern="^(open|all)$")):
    stmt = select(TryOnReport).options(*_REPORT_LOAD).order_by(TryOnReport.created_at.desc()).limit(100)
    if show == "open":
        stmt = stmt.where(TryOnReport.status == "open")
    return [_report_out(r) for r in (await db.execute(stmt)).scalars().all()]


@admin_router.post("/{report_id}/refund", response_model=AdminReportOut)
async def refund_report(report_id: str, _: AdminUser, db: DbSession):
    """Gives the try-on's credits back (once) and tells the shopper by email."""
    r = await _report(db, report_id)
    if r.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This report was already answered.")
    amount = r.job.credit_cost
    if amount > 0:
        await credit_service.refund(
            db, user_id=r.user_id, amount=amount, reference_type="tryon_job", reference_id=r.job_id,
            note="Refund: reported try-on checked by TryOnU",
        )
    r.status, r.credits_refunded = "refunded", amount
    await db.commit()
    r = await _report(db, report_id)
    await _tell_shopper(r, amount)
    return _report_out(r)


@admin_router.post("/{report_id}/dismiss", response_model=AdminReportOut)
async def dismiss_report(report_id: str, _: AdminUser, db: DbSession):
    r = await _report(db, report_id)
    if r.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This report was already answered.")
    r.status = "dismissed"
    await db.commit()
    return _report_out(await _report(db, report_id))


async def _tell_shopper(r: TryOnReport, amount: int) -> None:
    from app.email.registry import get_email_provider
    from app.email.templates import action_email, site_url

    if not r.user or amount <= 0:
        return
    text, page = action_email(
        "We've refunded your try-on",
        [f"We checked the try-on you reported and it wasn't right. {amount} credits are back in your account."],
        "Try again",
        site_url("/try"),
    )
    try:
        await get_email_provider().send(to=r.user.email, subject="Your TryOnU credits are back", text_body=text, html_body=page)
    except Exception as exc:  # noqa: BLE001 - the refund stands either way
        logger.warning("report_refund_email_failed", report_id=r.id, error=str(exc)[:200])
