"""Deciding what happens to a paid FASHN render nobody could verify.

Two ways a job lands here, both held rather than delivered or refunded
automatically:

* the render came back but failed a product check (the job has a stored
  render in review_payload);
* the job stalled after FASHN accepted it, so we never received the render
  (no review_payload yet).

A reviewer then approves (deliver the held render), refunds, or reconciles
against FASHN's own status. Every action is refused unless the job is still
pending, so none can happen twice.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.providers.fashn import FASHNTryOnProvider
from app.core.logging import logger
from app.models.enums import JobStatus
from app.models.product import Product
from app.models.tryon import TryOnJob, TryOnResult
from app.services import credit_service
from app.services.storage_service import get_storage, new_key
from app.services.tryon_direct.inputs import (
    DirectInputError,
    fetch_product_image,
    hires_product_url,
    require_hires_product,
)
from app.services.tryon_direct.qc import qc_gate, run_qc

PENDING = "pending"


class ReviewError(Exception):
    """A reviewer's request that cannot apply to this job right now."""


async def pending_reviews(db) -> list[TryOnJob]:  # noqa: ANN001
    rows = await db.execute(
        select(TryOnJob).where(TryOnJob.review_state == PENDING).order_by(TryOnJob.created_at.desc()).limit(200)
    )
    return list(rows.scalars().all())


async def _load(db, job_id: str) -> TryOnJob:  # noqa: ANN001
    row = await db.execute(
        select(TryOnJob)
        .where(TryOnJob.id == job_id)
        .options(selectinload(TryOnJob.user_photo), selectinload(TryOnJob.product).selectinload(Product.images))
    )
    job = row.scalar_one_or_none()
    if job is None:
        raise ReviewError("no such try-on job")
    return job


def _require_pending(job: TryOnJob) -> None:
    if job.review_state != PENDING:
        raise ReviewError(f"this job is not waiting for review (state: {job.review_state or 'none'})")


def _deliver(db, job: TryOnJob, payload: dict, reviewer_note: str) -> None:  # noqa: ANN001
    qc = payload["qc_report"]
    session_result = TryOnResult(
        job_id=job.id,
        storage_key=payload["storage_key"],
        image_url=get_storage().signed_url(payload["storage_key"]),
        width=payload.get("width"),
        height=payload.get("height"),
        qc_report=qc,
        engine_meta={**payload["engine_meta"], "review": reviewer_note},
    )
    db.add(session_result)
    job.status = JobStatus.COMPLETED
    job.error_message = None
    job.completed_at = datetime.now(timezone.utc)


async def approve(db, job_id: str, reviewer_id: str) -> TryOnJob:  # noqa: ANN001
    """Delivers the held render to the customer after a human has looked at it."""
    job = await _load(db, job_id)
    _require_pending(job)
    if not job.review_payload or not job.review_payload.get("storage_key"):
        raise ReviewError("nothing was held for this job — reconcile it against FASHN instead")
    _deliver(db, job, job.review_payload, f"approved by reviewer {reviewer_id}")
    job.review_state = "approved"
    await db.commit()
    logger.warning("tryon_review_approved", job_id=job.id, reviewer=reviewer_id)
    return job


async def refund(db, job_id: str, reviewer_id: str, note: str) -> TryOnJob:  # noqa: ANN001
    job = await _load(db, job_id)
    _require_pending(job)
    await credit_service.refund(
        db,
        user_id=job.user_id,
        amount=job.credit_cost,
        reference_type="tryon_job",
        reference_id=job.id,
        note=f"Reviewed refund by {reviewer_id}: {note}"[:255],
    )
    job.review_state = "refunded"
    job.status = JobStatus.FAILED
    await db.commit()
    logger.warning("tryon_review_refunded", job_id=job.id, reviewer=reviewer_id)
    return job


async def reconcile(db, job_id: str, reviewer_id: str, provider: FASHNTryOnProvider) -> str:  # noqa: ANN001
    """Asks FASHN what happened to a paid job we never received a render for.

    Reads status only: FASHN is never asked to create anything. Returns the
    outcome, one of: delivered, held, refunded, still_running, unreadable."""
    job = await _load(db, job_id)
    _require_pending(job)
    if job.review_payload and job.review_payload.get("storage_key"):
        raise ReviewError("this job already has a render held for review — approve or refund it")
    if not job.provider_job_id:
        raise ReviewError("this job never reached FASHN, so there is nothing to reconcile")
    if job.steps:
        raise ReviewError("a multi-product try-on is reviewed by hand: refund it, or approve nothing")

    try:
        status = await provider.fetch_status(job.provider_job_id)
    except Exception as exc:  # noqa: BLE001 — leave the job pending and say why
        logger.warning("tryon_review_status_failed", job_id=job.id, error=str(exc)[:200])
        return "unreadable"

    state = status.get("status")
    if state == "failed":
        await refund(db, job.id, reviewer_id, f"FASHN reports job {job.provider_job_id} failed")
        return "refunded"
    if state != "completed":
        return "still_running"

    outputs = status.get("output") or []
    if not outputs:
        return "unreadable"

    image_bytes, content_type = await provider.download_output(job.provider_job_id, outputs[0])
    person = get_storage().read(job.user_photo.storage_key)
    product_url = hires_product_url(job.product.primary_image_url or "")
    try:
        product = await fetch_product_image(product_url)
        require_hires_product(product)
    except DirectInputError as exc:
        logger.warning("tryon_review_product_unusable", job_id=job.id, error=str(exc)[:200])
        return "unreadable"
    qc = await run_qc(
        person, product, image_bytes, product_name=job.product.name, product_url=product_url, with_vlm=False
    )
    qc["gate"] = qc_gate(qc)

    ext = "jpg" if content_type == "image/jpeg" else content_type.split("/")[-1]
    key = new_key("tryon", "results", job.user_id, f"{job.id}.{ext}")
    get_storage().put(key, image_bytes, content_type)
    resolution = qc.get("resolution") or {}
    payload = {
        "storage_key": key,
        "qc_report": qc,
        "engine_meta": {
            "provider_job_id": job.provider_job_id,
            "engine_mode": "direct",
            "provider": "fashn",
            "model": job.provider_model,
            "product_id": job.product_id,
            "product_name": job.product.name,
            "product_image_url": product_url,
            "reconciled_by": reviewer_id,
        },
        "width": resolution.get("output_width"),
        "height": resolution.get("output_height"),
    }
    if qc["gate"]["passed"]:
        job.review_payload = payload
        _deliver(db, job, payload, f"reconciled by reviewer {reviewer_id}")
        job.review_state = "resolved"
        await db.commit()
        return "delivered"

    job.review_payload = payload
    job.review_reason = "verification failed: " + ", ".join(qc["gate"]["failed_checks"])
    await db.commit()
    return "held"
