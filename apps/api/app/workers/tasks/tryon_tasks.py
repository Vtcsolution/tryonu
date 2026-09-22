"""The actual AI try-on job execution — runs in the RQ worker process in
production, or as an in-process asyncio task in local dev (see
app/services/queue.py). Either way this async function is the single
source of truth for the job lifecycle: queued -> processing -> completed |
failed, with automatic credit refund on failure.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.providers.base import OutfitPiece, TryOnInput, TryOnProviderError
from app.ai.providers.registry import get_full_look_provider, get_tryon_provider
from app.core.config import get_settings
from app.core.logging import logger
from app.core.runtime_settings import refresh_if_stale
from app.db.session import AsyncSessionLocal
from app.models.ai_usage import AIUsage
from app.models.enums import AIUsageKind, JobStatus, OutfitSlot
from app.models.outfit import OutfitItem
from app.models.product import Product
from app.models.tryon import TryOnJob, TryOnResult
from app.services import credit_service
from app.services.face_restore import restore_face
from app.services.outfit_slots import (
    MAX_PROMPT,
    V16_CATEGORY,
    render_plan,
    renderable_slots,
    slot_for,
    worn_on_head,
)
from app.services.storage_service import get_storage, new_key
from app.services.tryon_quality.pipeline import LookItem, QualityFailure, RenderHint, keep_person, render_look

settings = get_settings()
MAX_ATTEMPTS = 3


def _renderable_slots(model: str, whole_outfit: bool = False) -> set[OutfitSlot]:
    return renderable_slots(model, whole_outfit)


def _absolute_url(url: str) -> str:
    if url.startswith("/"):
        return f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}{url}"
    return url


@dataclass(frozen=True, slots=True)
class _Layer:
    image_url: str
    slot: OutfitSlot | None  # None: a single item we know nothing about — let the model infer
    name: str = "the product"


async def _garment_layers(session, job: TryOnJob, model: str, whole_outfit: bool = False) -> list[_Layer]:
    if job.product is not None:
        img = job.product.primary_image_url
        return [_Layer(img, slot_for(job.product.name), job.product.name)] if img else []

    if job.wardrobe_item is not None:
        item = job.wardrobe_item
        return [_Layer(item.image_url, None, item.name)] if item.image_url else []

    if job.outfit_id is not None:
        result = await session.execute(
            select(OutfitItem)
            .where(OutfitItem.outfit_id == job.outfit_id)
            .options(selectinload(OutfitItem.product).selectinload(Product.images))
            .order_by(OutfitItem.position)
        )
        items = [i for i in result.scalars().all() if i.product and i.product.primary_image_url]
        plan = render_plan([(i.slot, i.product.name) for i in items], model, whole_outfit)
        return [_Layer(items[idx].product.primary_image_url, slot, items[idx].product.name) for idx, slot in plan]

    return []


def _quality_pipeline_on(provider) -> bool:  # noqa: ANN001
    # the mock provider returns a stamped placeholder, not a render of the
    # photo — there's nothing to merge or inspect
    return settings.TRYON_QUALITY_PIPELINE and provider.name != "mock"


def _data_uri(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()


def _look_item(layer: _Layer) -> LookItem:
    return LookItem(_absolute_url(layer.image_url), layer.slot or slot_for(layer.name), layer.name)


def _at_detail(provider):  # noqa: ANN001, ANN202
    """The same engine at its most detailed setting, for a second attempt at
    an item the inspector rejected. Everyday renders use the fast setting
    (measured: 25s against 425s for a four-item outfit), but that is what
    drew an ivory dress pink with flattened embroidery — worth the extra
    seconds once, rather than refusing the try-on."""
    at_quality = getattr(provider, "at_quality", None)
    return at_quality(settings.OPENAI_IMAGE_QUALITY_RETRY) if callable(at_quality) else provider


def _pipeline_renderer(provider):  # noqa: ANN001, ANN202
    """How the quality pipeline asks the provider for one item: on the
    pipeline's current image (not the previous raw render), with what the
    product is and the inspector's correction, a new seed per attempt, and
    the detailed setting once an attempt has failed."""

    async def render(base_jpeg: bytes, item: LookItem, hint: RenderHint) -> bytes:
        engine = _at_detail(provider) if hint.detail else provider
        if engine.whole_outfit:
            # OpenAI image editing: one product per call, on the pipeline's
            # current image; no seed parameter — each call differs anyway
            piece = OutfitPiece(
                item.image_url, item.slot.value, item.name, note=hint.fix, description=hint.description
            )
            return (await engine.generate_outfit(_data_uri(base_jpeg), [piece])).image_bytes
        payload = _tryon_input(_data_uri(base_jpeg), _Layer(item.image_url, item.slot, item.name), engine.model)
        if engine.model == "tryon-max" and hint.fix:
            payload = replace(payload, prompt=f"{payload.prompt} {hint.fix}".strip())
        output = await engine.generate(replace(payload, seed=hint.seed))
        return output.image_bytes

    return render


def _pipeline_render_all(provider):  # noqa: ANN001, ANN202
    """One render with every product of the look on it."""

    async def render_all(base_jpeg: bytes, items: list[LookItem], descriptions: list[str]) -> bytes:
        pieces = [
            OutfitPiece(image_url=i.image_url, slot=i.slot.value, name=i.name, description=d)
            for i, d in zip(items, descriptions)
        ]
        output = await provider.generate_outfit(_data_uri(base_jpeg), pieces)
        return output.image_bytes

    return render_all


async def _keep_person_if_on(job: TryOnJob, image: bytes, content_type: str, layers: list[_Layer]) -> tuple[bytes, str, bool]:
    """A whole-look render with the person's own pixels kept outside the
    products. (image, content type, whether the person was kept)."""
    if not settings.TRYON_QUALITY_PIPELINE:
        return image, content_type, False
    try:
        person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
        kept = await keep_person(person, image, [_look_item(layer) for layer in layers])
    except Exception as exc:  # noqa: BLE001 — never lose the render over this
        logger.warning("tryon_keep_person_failed", job_id=job.id, error=str(exc)[:300])
        return image, content_type, False
    return kept, "image/jpeg", True


def _outfit_pieces(layers: list[_Layer]) -> list[OutfitPiece]:
    return [
        OutfitPiece(image_url=_absolute_url(layer.image_url), slot=(layer.slot or OutfitSlot.TOP).value, name=layer.name)
        for layer in layers
    ]


def _tryon_input(model_url: str, layer: _Layer, model: str) -> TryOnInput:
    garment_url = _absolute_url(layer.image_url)
    if layer.slot is None:
        return TryOnInput(model_image_url=model_url, garment_image_url=garment_url)
    if model == "tryon-max":
        return TryOnInput(model_image_url=model_url, garment_image_url=garment_url, prompt=MAX_PROMPT.get(layer.slot, ""))
    return TryOnInput(
        model_image_url=model_url, garment_image_url=garment_url, category=V16_CATEGORY.get(layer.slot, "auto")
    )


async def run_tryon_job_async(job_id: str) -> None:
    await refresh_if_stale()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TryOnJob)
            .where(TryOnJob.id == job_id)
            .options(
                selectinload(TryOnJob.product).selectinload(Product.images),
                selectinload(TryOnJob.wardrobe_item),
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

        provider = get_tryon_provider()
        layers = await _garment_layers(session, job, provider.model, provider.whole_outfit)

        # A look the main provider can't fully draw (FASHN: no shoes, bags or
        # jewellery) goes to the whole-outfit provider first; if that fails
        # the job still completes with the main provider below.
        full = get_full_look_provider()
        if job.outfit_id is not None and full is not None and full is not provider:
            full_layers = await _garment_layers(session, job, full.model, True)
            if len(full_layers) > len(layers):
                try:
                    output = await full.generate_outfit(
                        _absolute_url(job.user_photo.url), _outfit_pieces(full_layers)
                    )
                except TryOnProviderError as exc:
                    logger.warning("tryon_full_look_failed_falling_back", job_id=job.id, error=str(exc)[:300])
                    session.add(
                        AIUsage(
                            user_id=job.user_id,
                            kind=AIUsageKind.VIRTUAL_TRYON,
                            provider=full.name,
                            model=full.model,
                            reference_type="tryon_job",
                            reference_id=job.id,
                            success=False,
                            error_message=str(exc)[:512],
                        )
                    )
                    await session.commit()
                else:
                    image, ctype, kept = await _keep_person_if_on(job, output.image_bytes, output.content_type, full_layers)
                    await _complete_job(
                        session, job, image, ctype, full.name, full.model,
                        drawn=[layer.name for layer in full_layers], face_kept=kept,
                    )
                    return

        if not layers:
            message = (
                "This outfit has no clothing item FASHN can render (only accessories, "
                "which aren't visually applied) — nothing to generate an image from"
                if job.outfit_id is not None
                else "No garment image available to try on"
            )
            await _fail_job(session, job, message, refund=True)
            return

        model_url = _absolute_url(job.user_photo.url)

        current_model_url = model_url
        final_bytes: bytes | None = None
        final_content_type = "image/jpeg"

        try:
            if provider.whole_outfit and not _quality_pipeline_on(provider):
                # one render with every item at once (shoes, bags, jewellery too)
                output = await provider.generate_outfit(model_url, _outfit_pieces(layers))
                image, ctype, kept = await _keep_person_if_on(job, output.image_bytes, output.content_type, layers)
                await _complete_job(
                    session, job, image, ctype, provider.name, provider.model,
                    drawn=[layer.name for layer in layers], face_kept=kept,
                )
                return

            if _quality_pipeline_on(provider):
                # render -> keep only the product -> inspect -> retry/refuse
                # (app/services/tryon_quality/pipeline.py)
                person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
                try:
                    image, _ = await render_look(
                        person,
                        [_look_item(layer) for layer in layers],
                        _pipeline_renderer(provider),
                        retries=settings.TRYON_QUALITY_RETRIES,
                        min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
                        min_other=settings.TRYON_QUALITY_MIN_FIT,
                        # OpenAI draws several products in one edit, so the
                        # whole look is one render and only failures get their
                        # own; it also edits any photo, so a failed watch is
                        # retried as a close-up. FASHN takes one product per
                        # call and needs a photo of a person.
                        render_all=_pipeline_render_all(provider) if provider.whole_outfit else None,
                        zoom_small=provider.whole_outfit,
                        budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
                    )
                except QualityFailure as exc:
                    await _fail_job(
                        session,
                        job,
                        f"We couldn't draw “{exc.item[:80]}” accurately enough, so no result was returned "
                        f"and your credits were refunded. Problem found: {'; '.join(exc.issues[:2]) or 'poor match'}. "
                        "Try another product photo, or a clearer full-body photo.",
                        refund=True,
                    )
                    return
                await _complete_job(
                    session, job, image, "image/jpeg", provider.name, provider.model,
                    drawn=[layer.name for layer in layers], face_kept=True,
                )
                return

            # Multi-item outfits are rendered as a sequential chain: each
            # garment is applied on top of the previous step's result.
            for layer in layers:
                output = await provider.generate(_tryon_input(current_model_url, layer, provider.model))
                final_bytes = output.image_bytes
                final_content_type = output.content_type

                if len(layers) > 1:
                    # stage the intermediate result so the next garment
                    # layers on top of it
                    interim_key = new_key("tryon", "interim", f"{job.id}-{len(final_bytes)}.jpg")
                    get_storage().put(interim_key, final_bytes, final_content_type)
                    current_model_url = _absolute_url(get_storage().signed_url(interim_key, ttl_seconds=600))

            await _complete_job(
                session, job, final_bytes, final_content_type, provider.name, provider.model,
                drawn=[layer.name for layer in layers],
            )

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
                    error_message=str(exc)[:512],  # AIUsage.error_message is VARCHAR(512)
                )
            )
            await session.commit()


async def _with_original_face(
    job: TryOnJob, image_bytes: bytes, content_type: str, drawn: list[str]
) -> tuple[bytes, str]:
    """The result with the person's own face blended back in, or unchanged
    if that's off or can't be done safely. Never fails the job."""
    if not settings.TRYON_KEEP_ORIGINAL_FACE or job.user_photo is None:
        return image_bytes, content_type
    if any(worn_on_head(name) for name in drawn):
        # a hat, sunglasses, earrings… were just drawn on the head — the
        # original head would paint over them
        logger.info("tryon_face_restore_skipped_head_item", job_id=job.id)
        return image_bytes, content_type
    try:
        original = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
        restored = await asyncio.to_thread(restore_face, original, image_bytes)
    except Exception as exc:  # noqa: BLE001 — a failed restore must never lose the render
        logger.warning("tryon_face_restore_failed", job_id=job.id, error=str(exc)[:300])
        return image_bytes, content_type
    if restored is None:
        logger.info("tryon_face_restore_skipped", job_id=job.id)
        return image_bytes, content_type
    return restored, "image/jpeg"


async def _complete_job(  # noqa: ANN001
    session,
    job: TryOnJob,
    image_bytes: bytes,
    content_type: str,
    provider_name: str,
    provider_model: str,
    *,
    drawn: list[str] = (),  # type: ignore[assignment]
    face_kept: bool = False,
) -> None:
    if not face_kept:  # the quality pipeline already kept the person's own face
        image_bytes, content_type = await _with_original_face(job, image_bytes, content_type, list(drawn))
    ext = "jpg" if content_type == "image/jpeg" else content_type.split("/")[-1]
    key = new_key("tryon", "results", job.user_id, f"{job.id}.{ext}")
    storage = get_storage()
    storage.put(key, image_bytes, content_type)
    url = storage.signed_url(key)

    session.add(TryOnResult(job_id=job.id, storage_key=key, image_url=url))
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    # the engine that actually drew it — the one recorded at creation can be
    # stale if the provider was switched while the job was queued
    job.provider = provider_name
    job.provider_model = provider_model

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
            error_message=str(exc)[:512],  # AIUsage.error_message is VARCHAR(512)
        )
    )
    await _fail_job(session, job, str(exc), refund=True)


async def _fail_job(session, job: TryOnJob, message: str, *, refund: bool) -> None:  # noqa: ANN001
    # Real bug, found via flaky-test investigation: this used to be two
    # separate commits (status, then refund). A reader on a different
    # session/connection (e.g. the frontend polling the job, or a test
    # checking the balance right after seeing "failed") could observe the
    # job as failed *before* the refund had landed — a real, if narrow,
    # "where are my credits" moment. One commit makes both changes atomic:
    # an external reader sees either neither or both, never the gap.
    job.status = JobStatus.FAILED
    job.error_message = message[:2000]
    job.completed_at = datetime.now(timezone.utc)

    if refund:
        await credit_service.refund(
            session,
            user_id=job.user_id,
            amount=job.credit_cost,
            reference_type="tryon_job",
            reference_id=job.id,
        )

    await session.commit()
    logger.error("tryon_job_failed", job_id=job.id, error=message)


def run_tryon_job(job_id: str) -> None:
    """Sync entrypoint RQ calls in the worker process."""
    asyncio.run(run_tryon_job_async(job_id))
