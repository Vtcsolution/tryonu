"""The actual AI try-on job execution — runs in the RQ worker process in
production, or as an in-process asyncio task in local dev (see
app/services/queue.py). Either way this async function is the single
source of truth for the job lifecycle: queued -> processing -> completed |
failed, with automatic credit refund on failure.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.providers.base import TryOnInput, TryOnProviderError
from app.ai.providers.registry import get_tryon_provider
from app.core.config import get_settings
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.ai_usage import AIUsage
from app.models.enums import AIUsageKind, JobStatus
from app.models.outfit import OutfitItem
from app.models.product import Product
from app.models.tryon import TryOnJob, TryOnResult
from app.services import credit_service
from app.services.storage_service import get_storage, new_key

settings = get_settings()
MAX_ATTEMPTS = 3


def _absolute_url(url: str) -> str:
    if url.startswith("/"):
        return f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}{url}"
    return url


async def _garment_image_urls(session, job: TryOnJob) -> list[str]:
    if job.product is not None:
        img = job.product.primary_image_url
        return [img] if img else []

    if job.outfit_id is not None:
        result = await session.execute(
            select(OutfitItem)
            .where(OutfitItem.outfit_id == job.outfit_id)
            .options(selectinload(OutfitItem.product).selectinload(Product.images))
            .order_by(OutfitItem.position)
        )
        items = result.scalars().all()
        return [i.product.primary_image_url for i in items if i.product and i.product.primary_image_url]

    return []


async def run_tryon_job_async(job_id: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TryOnJob)
            .where(TryOnJob.id == job_id)
            .options(
                selectinload(TryOnJob.product).selectinload(Product.images),
                selectinload(TryOnJob.user_photo),
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("tryon_job_not_found", job_id=job_id)
            return
        if job.status != JobStatus.QUEUED:
            logger.info("tryon_job_skip_not_queued", job_id=job_id, status=job.status.value)
            return

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

        garment_urls = await _garment_image_urls(session, job)
        if not garment_urls:
            await _fail_job(session, job, "No product image available to try on", refund=True)
            return

        model_url = _absolute_url(job.user_photo.url)
        provider = get_tryon_provider()

        current_model_url = model_url
        final_bytes: bytes | None = None
        final_content_type = "image/jpeg"

        try:
            # Multi-item outfits are rendered as a sequential chain: each
            # garment is applied on top of the previous step's result.
            for garment_url in garment_urls:
                output = await provider.generate(
                    TryOnInput(model_image_url=current_model_url, garment_image_url=_absolute_url(garment_url))
                )
                final_bytes = output.image_bytes
                final_content_type = output.content_type

                if len(garment_urls) > 1:
                    # stage the intermediate result so the next garment
                    # layers on top of it
                    interim_key = new_key("tryon", "interim", f"{job.id}-{len(final_bytes)}.jpg")
                    get_storage().put(interim_key, final_bytes, final_content_type)
                    current_model_url = _absolute_url(get_storage().signed_url(interim_key, ttl_seconds=600))

            await _complete_job(session, job, final_bytes, final_content_type, provider.name, provider.model)

        except TryOnProviderError as exc:
            await _handle_provider_error(session, job, exc, provider.name, provider.model)
        except Exception as exc:  # noqa: BLE001 — never let an unexpected error strand a job as "processing"
            logger.error("tryon_job_unexpected_error", job_id=job_id, error=str(exc))
            await _fail_job(session, job, f"Unexpected error: {exc}", refund=True)
            session.add(
                AIUsage(
                    user_id=job.user_id,
                    kind=AIUsageKind.VIRTUAL_TRYON,
                    provider=provider.name,
                    model=provider.model,
                    reference_type="tryon_job",
                    reference_id=job.id,
                    success=False,
                    error_message=str(exc),
                )
            )
            await session.commit()


async def _complete_job(session, job: TryOnJob, image_bytes: bytes, content_type: str, provider_name: str, provider_model: str) -> None:  # noqa: ANN001
    ext = "jpg" if content_type == "image/jpeg" else content_type.split("/")[-1]
    key = new_key("tryon", "results", job.user_id, f"{job.id}.{ext}")
    storage = get_storage()
    storage.put(key, image_bytes, content_type)
    url = storage.signed_url(key)

    session.add(TryOnResult(job_id=job.id, storage_key=key, image_url=url))
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(timezone.utc)

    session.add(
        AIUsage(
            user_id=job.user_id,
            kind=AIUsageKind.VIRTUAL_TRYON,
            provider=provider_name,
            model=provider_model,
            reference_type="tryon_job",
            reference_id=job.id,
            success=True,
        )
    )
    await session.commit()
    logger.info("tryon_job_completed", job_id=job.id)


async def _handle_provider_error(session, job: TryOnJob, exc: TryOnProviderError, provider_name: str, provider_model: str) -> None:  # noqa: ANN001
    if exc.retryable and job.attempt < MAX_ATTEMPTS:
        job.attempt += 1
        job.status = JobStatus.QUEUED
        await session.commit()
        logger.warning("tryon_job_retrying", job_id=job.id, attempt=job.attempt, error=str(exc))

        from app.services.queue import enqueue_tryon_job

        backoff = min(2**job.attempt, 20)
        await asyncio.sleep(backoff)
        enqueue_tryon_job(job.id)
        return

    session.add(
        AIUsage(
            user_id=job.user_id,
            kind=AIUsageKind.VIRTUAL_TRYON,
            provider=provider_name,
            model=provider_model,
            reference_type="tryon_job",
            reference_id=job.id,
            success=False,
            error_message=str(exc),
        )
    )
    await _fail_job(session, job, str(exc), refund=True)


async def _fail_job(session, job: TryOnJob, message: str, *, refund: bool) -> None:  # noqa: ANN001
    job.status = JobStatus.FAILED
    job.error_message = message[:2000]
    job.completed_at = datetime.now(timezone.utc)
    await session.commit()
    logger.error("tryon_job_failed", job_id=job.id, error=message)

    if refund:
        await credit_service.refund(
            session,
            user_id=job.user_id,
            amount=job.credit_cost,
            reference_type="tryon_job",
            reference_id=job.id,
        )
        await session.commit()


def run_tryon_job(job_id: str) -> None:
    """Sync entrypoint RQ calls in the worker process."""
    asyncio.run(run_tryon_job_async(job_id))
