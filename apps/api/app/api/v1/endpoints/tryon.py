from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.providers.registry import get_tryon_provider
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.db.base import new_uuid
from app.models.enums import CreditReason, JobStatus
from app.models.outfit import Outfit, OutfitItem
from app.models.photo import UserPhoto
from app.models.product import Product
from app.models.tryon import TryOnJob
from app.schemas.common import Page
from app.schemas.tryon import CreateMultiTryOnRequest, CreateTryOnRequest, TryOnJobOut
from app.services import credit_service
from app.services.credit_service import InsufficientCreditsError
from app.services.queue import enqueue_tryon_job

router = APIRouter(prefix="/tryon", tags=["try-on"])
settings = get_settings()

_LOAD_OPTS = (
    selectinload(TryOnJob.product).selectinload(Product.images),
    selectinload(TryOnJob.product).selectinload(Product.retailer),
    selectinload(TryOnJob.outfit).selectinload(Outfit.items).selectinload(OutfitItem.product).selectinload(Product.images),
    selectinload(TryOnJob.outfit).selectinload(Outfit.items).selectinload(OutfitItem.product).selectinload(Product.retailer),
    selectinload(TryOnJob.result),
    selectinload(TryOnJob.user_photo),
)

_tryon_rate_limit = Depends(rate_limiter("tryon_create", limit=settings.RATE_LIMIT_TRYON_PER_HOUR, window_seconds=3600))


async def _resolve_product_or_outfit(db: DbSession, user: CurrentUser, *, product_id: str | None, outfit_id: str | None) -> int:
    """Validates exactly one of product/outfit is a real, owned/active
    target and returns the per-job credit cost — shared by the single and
    multi-photo creation endpoints so they can never drift apart."""
    if bool(product_id) == bool(outfit_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Provide exactly one of product_id or outfit_id"
        )
    if product_id:
        product = await db.get(Product, product_id)
        if product is None or not product.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return settings.TRYON_CREDIT_COST

    outfit = await db.get(Outfit, outfit_id)
    if outfit is None or outfit.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outfit not found")
    return settings.OUTFIT_TRYON_CREDIT_COST


async def _load_owned_photo(db: DbSession, user: CurrentUser, photo_id: str) -> UserPhoto:
    photo = await db.get(UserPhoto, photo_id)
    if photo is None or photo.user_id != user.id or photo.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitting profile photo not found")
    return photo


async def _create_one_job(
    db: DbSession, user: CurrentUser, *, photo: UserPhoto, product_id: str | None, outfit_id: str | None, cost: int
) -> str:
    provider = get_tryon_provider()
    job_id = new_uuid()

    # Debit first: if the user can't afford it, no job row is ever created.
    await credit_service.debit(
        db,
        user_id=user.id,
        amount=cost,
        reason=CreditReason.TRYON_DEBIT,
        reference_type="tryon_job",
        reference_id=job_id,
        note=f"Try-on ({'product' if product_id else 'outfit'})",
    )

    job = TryOnJob(
        id=job_id,
        user_id=user.id,
        user_photo_id=photo.id,
        product_id=product_id,
        outfit_id=outfit_id,
        provider=provider.name,
        provider_model=provider.model,
        status=JobStatus.QUEUED,
        credit_cost=cost,
        queued_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
    enqueue_tryon_job(job.id)
    return job_id


async def _load_job(db: DbSession, job_id: str) -> TryOnJob:
    result = await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(*_LOAD_OPTS))
    return result.scalar_one()


@router.post("", response_model=TryOnJobOut, status_code=status.HTTP_201_CREATED, dependencies=[_tryon_rate_limit])
async def create_tryon(payload: CreateTryOnRequest, user: CurrentUser, db: DbSession):
    cost = await _resolve_product_or_outfit(db, user, product_id=payload.product_id, outfit_id=payload.outfit_id)
    photo = await _load_owned_photo(db, user, payload.user_photo_id)
    job_id = await _create_one_job(
        db, user, photo=photo, product_id=payload.product_id, outfit_id=payload.outfit_id, cost=cost
    )
    return await _load_job(db, job_id)


@router.post("/multi", response_model=list[TryOnJobOut], status_code=status.HTTP_201_CREATED, dependencies=[_tryon_rate_limit])
async def create_tryon_multi(payload: CreateMultiTryOnRequest, user: CurrentUser, db: DbSession):
    """One job per photo (e.g. front + back angles), same product/outfit —
    for showing "how it looks from the front and the back" side by side.
    Charged per job; the whole batch's cost is checked against the
    current balance up front, so a partway insufficient-credits failure
    can never leave the user with only some of the angles they asked for
    and paid for."""
    if len(payload.user_photo_ids) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide at least 2 photos, or use POST /tryon for one")
    if len(set(payload.user_photo_ids)) != len(payload.user_photo_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate photo ids")

    cost = await _resolve_product_or_outfit(db, user, product_id=payload.product_id, outfit_id=payload.outfit_id)
    photos = [await _load_owned_photo(db, user, pid) for pid in payload.user_photo_ids]

    total_cost = cost * len(photos)
    balance = await credit_service.get_balance(db, user.id)
    if balance < total_cost:
        raise InsufficientCreditsError(required=total_cost, available=balance)

    job_ids = [
        await _create_one_job(db, user, photo=photo, product_id=payload.product_id, outfit_id=payload.outfit_id, cost=cost)
        for photo in photos
    ]
    return [await _load_job(db, job_id) for job_id in job_ids]


@router.get("", response_model=Page[TryOnJobOut])
async def list_tryon_jobs(user: CurrentUser, db: DbSession, limit: int = 20, offset: int = 0):
    base = select(TryOnJob).where(TryOnJob.user_id == user.id)

    count_result = await db.execute(select(TryOnJob.id).where(TryOnJob.user_id == user.id))
    total = len(count_result.all())

    result = await db.execute(
        base.options(*_LOAD_OPTS).order_by(TryOnJob.created_at.desc()).limit(limit).offset(offset)
    )
    return Page(items=list(result.scalars().all()), total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=TryOnJobOut)
async def get_tryon_job(job_id: str, user: CurrentUser, db: DbSession):
    result = await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(*_LOAD_OPTS))
    job = result.scalar_one_or_none()
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on job not found")
    return job


@router.post("/{job_id}/cancel", response_model=TryOnJobOut)
async def cancel_tryon_job(job_id: str, user: CurrentUser, db: DbSession):
    result = await db.execute(select(TryOnJob).where(TryOnJob.id == job_id).options(*_LOAD_OPTS))
    job = result.scalar_one_or_none()
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on job not found")
    if job.status not in (JobStatus.QUEUED, JobStatus.PROCESSING):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job already finished")

    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    await credit_service.refund(
        db,
        user_id=user.id,
        amount=job.credit_cost,
        reference_type="tryon_job",
        reference_id=job.id,
        note="Refund — cancelled by user",
    )
    await db.commit()
    await db.refresh(job)
    return job
