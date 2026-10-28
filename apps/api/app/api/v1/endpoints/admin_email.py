"""Admin → Send email: write to one person, every member who gets emails,
every shop owner or the team, from the site's own address."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import AdminUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.admin_email import AdminEmail
from app.services import admin_email_service as svc
from app.services import email_budget

router = APIRouter(prefix="/admin/email", tags=["admin"])


class AudiencesOut(BaseModel):
    members: int
    stores: int
    team: int
    max_per_send: int
    per_hour: int  # how fast group emails go out
    per_day: int  # the most the site sends in a day (group emails and the daily email)
    sent_today: int
    sending_ready: bool  # the site can send email (Settings → Email is filled in)
    from_address: str


class SendIn(BaseModel):
    audience: str = Field(pattern="^(one|me|members|stores|team)$")
    to: EmailStr | None = None  # audience "one"
    subject: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=2, max_length=20000)
    # None: a plain message; "looks": the trending Ready looks below the message
    template: str | None = Field(default=None, pattern="^looks$")


class PreviewIn(BaseModel):
    subject: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=20000)
    template: str | None = Field(default=None, pattern="^looks$")


class AdminEmailOut(BaseModel):
    id: str
    audience: str
    template: str | None = None
    to_address: str | None
    subject: str
    total: int
    sent: int
    failed: int
    status: str  # queued | sending | paused | done
    paused_until: datetime | None = None
    last_error: str | None = None
    created_at: datetime


def _out(row: AdminEmail) -> AdminEmailOut:
    return AdminEmailOut(
        id=row.id, audience=row.audience, template=row.template, to_address=row.to_address, subject=row.subject, total=row.total,
        sent=row.sent, failed=row.failed, status=row.status, paused_until=row.paused_until,
        last_error=row.last_error if row.status == "paused" else None, created_at=row.created_at,
    )


@router.get("/audiences", response_model=AudiencesOut)
async def audiences(me: AdminUser, db: DbSession):
    s = get_settings()
    return AudiencesOut(
        members=len(await svc.recipients(db, "members", me=me)),
        stores=len(await svc.recipients(db, "stores", me=me)),
        team=len(await svc.recipients(db, "team", me=me)),
        max_per_send=svc.MAX_PER_SEND,
        per_hour=s.EMAIL_PER_HOUR,
        per_day=s.EMAIL_PER_DAY,
        sent_today=await email_budget.used_today(db),
        sending_ready=s.EMAIL_PROVIDER == "smtp" and bool(s.SMTP_HOST),
        from_address=s.SMTP_FROM_EMAIL,
    )


@router.post(
    "/send",
    response_model=AdminEmailOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("admin_email", limit=60, window_seconds=3600))],
)
async def send(payload: SendIn, me: AdminUser, db: DbSession):
    """One person (or a test to yourself) is sent now; a group goes in the
    queue and out slowly (EMAIL_PER_HOUR), its progress shown in the list."""
    if payload.audience == "one" and not payload.to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Type the email address to send to.")
    people = await svc.recipients(db, payload.audience, me=me, address=str(payload.to) if payload.to else None)
    if not people:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nobody to send this to yet.")
    if len(people) > svc.MAX_PER_SEND:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"That's {len(people)} people. One email can go to at most {svc.MAX_PER_SEND}.",
        )
    looks = None
    if payload.template == "looks":
        from app.services.looks_email import pick_looks

        looks = await pick_looks(db, f"{payload.subject} {payload.message}")
        if not looks:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There are no published Ready looks to show yet.")
    row = AdminEmail(
        audience=payload.audience, to_address=people[0].email if payload.audience in ("one", "me") else None,
        subject=payload.subject.strip(), message=payload.message.strip(), template=payload.template,
        total=len(people), created_by_id=me.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    if payload.audience in ("one", "me"):
        if not await email_budget.take(db):
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Today's email limit is reached (Settings → Email → Emails a day). It starts again at midnight (UTC).",
            )
        try:
            await svc.send_one(people[0], row.subject, row.message, row.audience, looks)
            row.sent, row.status = 1, "done"
        except Exception as exc:  # noqa: BLE001 - said plainly to the admin
            row.failed, row.status = 1, "done"
            await db.commit()
            hint = (
                "The mailbox host asked to slow down or refused the sign-in. Wait an hour; if it keeps happening, "
                "check the password in Settings → Email and that the mailbox isn't blocked in Hostinger."
                if email_budget.slow_down(exc)
                else "Check the address and Settings → Email."
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=f"The email couldn't be sent: {str(exc)[:160]}. {hint}"
            ) from exc
        await db.commit()
        return _out(row)
    svc.queued_row(row, people, looks)
    await db.commit()
    return _out(row)


@router.post("/preview")
async def preview(payload: PreviewIn, me: AdminUser, db: DbSession):
    """The email as a member would see it (with your first name), nothing sent."""
    looks = None
    if payload.template == "looks":
        from app.services.looks_email import pick_looks

        looks = await pick_looks(db, f"{payload.subject} {payload.message}")
    _, page = svc.render(
        payload.subject or "Preview", payload.message or " ", svc._first(me.full_name),
        unsubscribe_url="https://api.tryonu.app/api/v1/notifications/unsubscribe", audience="members", looks=looks,
    )
    return {"html": page}


@router.get("/history", response_model=list[AdminEmailOut])
async def history(_: AdminUser, db: DbSession):
    rows = (await db.execute(select(AdminEmail).order_by(AdminEmail.created_at.desc()).limit(50))).scalars().all()
    return [_out(r) for r in rows]
