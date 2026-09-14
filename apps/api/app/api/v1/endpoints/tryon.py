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
from app.schemas.tryon import CreateTryOnRequest, TryOnJobOut
from app.services import credit_service
from app.services.queue import enqueue_tryon_job

router = APIRouter(prefix="/tryon", tags=["try-on"])
settings = get_settings()

_LOAD_OPTS = (
    selectinload(TryOnJob.product).selectinload(Product.images),
    selectinload(TryOnJob.product).selectinload(Product.retailer),
    selectinload(TryOnJob.outfit).selectinload(Outfit.items).selectinload(OutfitItem.product).selectinload(Product.images),
    selectinload(TryOnJob.outfit).selectinload(Outfit.items).selectinload(OutfitItem.product).selectinload(Product.retailer),
    selectinload(TryOnJob.result),
)


@router.post(
    "",
    response_model=TryOnJobOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(rate_limiter("tryon_create", limit=settings.RATE_LIMIT_TRYON_PER_HOUR, window_seconds=3600))
    ],
)
async def create_tryon(payload: CreateTryOnRequest, user: CurrentUser, db: DbSession):
    if bool(payload.product_id) == bool(payload.outfit_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Provide exactly one of product_id or outfit_id"
        )

    photo = await db.get(UserPhoto, payload.user_photo_id)
    if photo is None or photo.user_id != user.id or photo.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitting profile photo not found")

    cost = settings.TRYON_CREDIT_COST

    if payload.product_id:
        product = await db.get(Product, payload.product_id)
        if product is None or not product.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    else:
        outfit = await db.get(Outfit, payload.outfit_id)
        if outfit is None or outfit.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outfit not found")
        cost = settings.OUTFIT_TRYON_CREDIT_COST

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
        note=f"Try-on ({'product' if payload.product_id else 'outfit'})",
    )

    job = TryOnJob(
        id=job_id,
        user_id=user.id,
        user_photo_id=photo.id,
        product_id=payload.product_id,
        outfit_id=payload.outfit_id,
        provider=provider.name,
        provider_model=provider.model,
        status=JobStatus.QUEUED,
        credit_cost=cost,
        queued_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()

    enqueue_tryon_job(job.id)

    result = await db.execute(select(TryOnJob).where(TryOnJob.id == job.id).options(*_LOAD_OPTS))
    return result.scalar_one()


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
