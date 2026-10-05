"""The actual AI try-on job execution — runs in the RQ worker process in
production, or as an in-process asyncio task in local dev (see
app/services/queue.py). Either way this async function is the single
source of truth for the job lifecycle: queued -> processing -> completed |
failed, with automatic credit refund on failure.
"""

from __future__ import annotations

import asyncio
import io
import base64
from dataclasses import dataclass, replace
from datetime import datetime, timezone

import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.providers.base import OutfitPiece, TryOnInput, TryOnOutput, TryOnProviderError, VirtualTryOnProvider
from app.ai.providers.gemini_image import GeminiImageTryOnProvider
from app.ai.providers.openai_image import OpenAIImageTryOnProvider
from app.ai.providers.registry import direct_engine_active, get_full_look_provider, get_tryon_provider
from app.core.config import get_settings
from app.core.logging import logger
from app.core.runtime_settings import refresh_if_stale
from app.db.session import AsyncSessionLocal
from app.models.ai_usage import AIUsage
from app.models.enums import AIUsageKind, JobStatus, OutfitSlot
from app.models.outfit import OutfitItem
from app.models.product import Product
from app.models.tryon import TryOnJob, TryOnResult
from app.models.user import User
from app.services import credit_service
from app.services.face_restore import restore_face
from app.services.outfit_slots import (
    LAYER_ORDER,
    effective_slot,
    MAX_PROMPT,
    V16_CATEGORY,
    render_plan,
    renderable_slots,
    slot_for,
    worn_on_head,
)
from app.services.storage_service import get_storage, new_key
from app.services.tryon_direct.final_check import final_check
from app.services.tryon_direct.orchestrate import (
    OrchestrationRefused,
    ProductInput,
    check_plan,
    credits_per_render,
    run_sequence,
    verify_step,
)
from app.services.tryon_direct.inputs import (
    DirectInputError,
    fetch_product_image,
    hires_product_url,
    require_hires_product,
    sniff_mime,
    to_data_uri,
)
from app.services.tryon_quality.compose import decode
from app.services.tryon_quality.debug_capture import DebugCapture
from app.services.tryon_quality.distractor_rank import log_distractor_rank, rank_against_distractors
from app.services.tryon_quality.masked import render_masked_look
from app.services.tryon_quality.pipeline import (
    render_whole_look,
    ItemReport,
    LookItem,
    QualityFailure,
    RenderHint,
    _download,
    keep_person,
    render_look,
    score_reports,
)
from app.services.tryon_quality.zoned import BatchMaskedRenderFn, render_zoned_look

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
    product_id: str | None = None  # so the result view can tie a label to its product card


async def _garment_layers(session, job: TryOnJob, model: str, whole_outfit: bool = False) -> list[_Layer]:
    if job.product is not None:
        img = job.product.primary_image_url
        return [_Layer(img, slot_for(job.product.name), job.product.name, job.product.id)] if img else []

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
        return [
            _Layer(items[idx].product.primary_image_url, slot, items[idx].product.name, items[idx].product.id)
            for idx, slot in plan
        ]

    return []


async def _direct_layers(session, job: TryOnJob) -> tuple[list[_Layer], list[str]]:  # noqa: ANN001
    """Every product the shopper selected, in layering order (base garments,
    then layers over them, then shoes and accessories). Unlike render_plan,
    nothing is dropped for sharing a slot with another item: the shopper chose
    it, so it is sent. Returns (layers, names of selected products that have
    no image and so cannot be sent at all)."""
    if job.outfit_id is None:
        layers = await _garment_layers(session, job, "tryon-max")
        missing = [] if layers or job.product is None else [job.product.name]
        return layers, missing
    result = await session.execute(
        select(OutfitItem)
        .where(OutfitItem.outfit_id == job.outfit_id)
        .options(selectinload(OutfitItem.product).selectinload(Product.images))
        .order_by(OutfitItem.position)
    )
    items = [i for i in result.scalars().all() if i.product is not None]
    missing = [i.product.name for i in items if not i.product.primary_image_url]
    usable = [i for i in items if i.product.primary_image_url]
    ordered = sorted(
        enumerate(usable),
        key=lambda pair: (LAYER_ORDER.get(effective_slot(pair[1].slot, pair[1].product.name), 9), pair[0]),
    )
    layers = [
        _Layer(i.product.primary_image_url, effective_slot(i.slot, i.product.name), i.product.name, i.product.id)
        for _, i in ordered
    ]
    return layers, missing


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


def _pipeline_edit_masked(provider):  # noqa: ANN001, ANN202
    """How the masked pipeline asks the provider to draw one item: on the
    pipeline's current image, only inside the given mask, at the cheaper
    setting unless this item has already failed once (see _at_detail)."""

    async def edit(person_png: bytes, mask_png: bytes, item: LookItem, hint: RenderHint) -> bytes:
        engine = _at_detail(provider) if hint.detail else provider
        piece = OutfitPiece(item.image_url, item.slot.value, item.name, note=hint.fix, description=hint.description)
        return (await engine.edit_masked(person_png, mask_png, piece)).image_bytes

    return edit


def _pipeline_edit_masked_batch(provider):  # noqa: ANN001, ANN202
    """How the zoned pipeline asks the provider to draw several items in
    one call — see app/services/tryon_quality/zoned.py and
    edit_masked_batch()'s own docstring for what this trades away."""

    async def edit_batch(person_png: bytes, mask_png: bytes, pieces) -> bytes:  # noqa: ANN001
        engine = _at_detail(provider) if any(p.detail for p in pieces) else provider
        outfit_pieces = [
            OutfitPiece(p.item.image_url, p.item.slot.value, p.item.name, note=p.fix, description=p.description)
            for p in pieces
        ]
        return (await engine.edit_masked_batch(person_png, mask_png, outfit_pieces)).image_bytes

    return edit_batch


def _pipeline_edit_batch_whole(provider):  # noqa: ANN001, ANN202
    """How the zoned pipeline asks a provider with no real masking
    (Gemini — confirmed 2026-10-02 against ai.google.dev: it "interprets
    editing instructions without requiring masks or layers", i.e. there is
    no mask parameter to give it) to draw a batch: a whole-image edit,
    `mask_png` ignored entirely. This does not weaken zoned.py's own
    pixel-lock guarantee — `_paste()` already only ever takes each
    accepted item's own region out of whatever a batch call returns, the
    same protection render_whole_look already relies on for this exact
    provider."""

    async def edit_batch(person_png: bytes, mask_png: bytes, pieces) -> bytes:  # noqa: ANN001, ARG001
        outfit_pieces = [
            OutfitPiece(p.item.image_url, p.item.slot.value, p.item.name, note=p.fix, description=p.description)
            for p in pieces
        ]
        return (await provider.generate_outfit(_data_uri(person_png), outfit_pieces)).image_bytes

    return edit_batch


def _pipeline_edit_batch_by_zone(
    routes: dict[str, BatchMaskedRenderFn], default: BatchMaskedRenderFn
) -> BatchMaskedRenderFn:
    """Routes each batch to a different provider adapter by the zone its
    pieces belong to (zoned.py's own BatchPiece.zone) — task: "use the
    better provider for each zone (e.g. one for garments, the other for
    small accessories)". A batch never mixes zones (see zoned.py's
    _zone_batches), so every piece in one call shares the same zone and
    therefore the same route."""

    async def edit_batch(person_png: bytes, mask_png: bytes, pieces) -> bytes:  # noqa: ANN001
        zone = pieces[0].zone if pieces else None
        route = routes.get(zone, default)
        return await route(person_png, mask_png, pieces)

    return edit_batch


def _progress_writer(session, job: TryOnJob):  # noqa: ANN001, ANN202
    """Writes what the render is doing onto the job the client polls."""

    async def write(message: str) -> None:
        job.progress = message[:160]
        await session.commit()

    return write


async def _render_with_engine(
    provider: VirtualTryOnProvider, person: bytes, items: list[LookItem], debug: DebugCapture | None = None
) -> tuple[bytes, list[ItemReport]]:
    """One engine's full, independent attempt at the whole look — with its
    own retries — so it can be scored against another engine's attempt at
    the same look (see the VIRTUAL_TRYON_PROVIDER=best_of branch below).

    Runs whichever of these fits how the engine behaves, best guarantee
    first: real masked editing for an engine that supports it, the
    direct render for one that gives the person back untouched on its
    own, the merge-based pipeline for one that does neither. No progress
    is written here — two of these run concurrently against one job row,
    and committing from both at once isn't safe on one AsyncSession."""
    if provider.supports_masked_edit and settings.TRYON_RENDER_ENGINE == "zoned":
        return await render_zoned_look(
            person,
            items,
            _pipeline_edit_masked_batch(provider),
            retries=settings.TRYON_QUALITY_RETRIES,
            min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
            min_other=settings.TRYON_QUALITY_MIN_FIT,
            budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
            debug=debug,
        )
    if provider.supports_masked_edit:
        return await render_masked_look(
            person,
            items,
            _pipeline_edit_masked(provider),
            retries=settings.TRYON_QUALITY_RETRIES,
            min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
            min_other=settings.TRYON_QUALITY_MIN_FIT,
            budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
            debug=debug,
        )
    if provider.preserves_person:
        return await render_whole_look(
            person,
            items,
            _pipeline_render_all(provider),
            retries=settings.TRYON_QUALITY_RETRIES,
            min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
            min_other=settings.TRYON_QUALITY_MIN_FIT,
            budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
            debug=debug,
        )
    return await render_look(
        person,
        items,
        _pipeline_renderer(provider),
        retries=settings.TRYON_QUALITY_RETRIES,
        min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
        min_other=settings.TRYON_QUALITY_MIN_FIT,
        render_all=_pipeline_render_all(provider) if provider.whole_outfit else None,
        zoom_small=provider.whole_outfit,
        budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
        debug=debug,
    )


async def _keep_person_if_on(
    job: TryOnJob, image: bytes, content_type: str, layers: list[_Layer], debug: DebugCapture | None = None
) -> tuple[bytes, str, bool]:
    """A whole-look render with the person's own pixels kept outside the
    products. (image, content type, whether the person was kept)."""
    if not settings.TRYON_QUALITY_PIPELINE:
        return image, content_type, False
    try:
        person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
        kept = await keep_person(person, image, [_look_item(layer) for layer in layers], debug=debug)
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

        # Debug image capture (TRYON_SAVE_DEBUG): never for a production
        # user's photo — only the accounts in TRYON_DEBUG_USER_EMAILS, which
        # DebugCapture itself enforces. One extra by-id lookup per job, only
        # ever a no-op when the flag is off.
        user = await session.get(User, job.user_id)
        debug = DebugCapture(job.id, user.email if user else None)

        provider = get_tryon_provider()
        layers = await _garment_layers(session, job, provider.model, provider.whole_outfit)

        # TRYON_ENGINE_MODE=direct: one photo + one product -> FASHN -> its
        # output kept as it is. Checked before every other path so none of the
        # legacy pipelines (render_look, keep_person, restore_face, …) can
        # touch the result.
        if direct_engine_active():
            direct_layers, missing = await _direct_layers(session, job)
            if missing:
                await _fail_job(
                    session,
                    job,
                    "These selected products have no image, so they cannot be tried on: "
                    + ", ".join(missing)
                    + ". Nothing was sent to FASHN.",
                    refund=True,
                )
                return
            await _run_direct_job(session, job, provider, direct_layers)
            return

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
                    image, ctype, kept = await _keep_person_if_on(job, output.image_bytes, output.content_type, full_layers, debug)
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
            if settings.VIRTUAL_TRYON_PROVIDER == "best_of":
                # Checked first, ahead of every other branch below, so it
                # never depends on what a plain get_tryon_provider() call
                # would have done with this look — it builds both real
                # engines itself and renders with both.
                person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
                items = [_look_item(layer) for layer in layers]
                engines: list[VirtualTryOnProvider] = [
                    OpenAIImageTryOnProvider(
                        api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
                        model=settings.OPENAI_IMAGE_MODEL,
                        quality=settings.OPENAI_IMAGE_QUALITY,
                    ),
                    GeminiImageTryOnProvider(
                        api_key=settings.GEMINI_API_KEY,  # type: ignore[arg-type]
                        model=settings.GEMINI_IMAGE_MODEL,
                        image_size=settings.GEMINI_IMAGE_SIZE,
                    ),
                ]
                async def _attempt(engine: VirtualTryOnProvider):
                    try:
                        image, reports = await _render_with_engine(engine, person, items, debug)
                        return engine.name, engine.model, image, reports, score_reports(reports)
                    except Exception as exc:  # noqa: BLE001 — collected below, not raised here
                        logger.warning(
                            "tryon_best_of_engine_failed",
                            job_id=job.id, engine=engine.name, error=str(exc)[:200],
                        )
                        return exc

                await _progress_writer(session, job)("Drawing the look")
                attempts = [await _attempt(engines[0])]
                won: list[tuple[str, str, bytes, list[ItemReport], float]] = (
                    [] if isinstance(attempts[0], BaseException) else [attempts[0]]
                )

                # A second full render is real, doubled spend on both
                # OpenAI and Gemini: its own per-item retries, its own
                # describe_product()/judge() vision calls, on top of the
                # first engine's — not "another try," a second whole job's
                # worth of API calls. Worth it only when the first left a
                # real question open: something it never got the chance to
                # judge at all, or a score low enough a second opinion
                # could actually change which one ships.
                skip_second = won and all(r.verdict is not None for r in won[0][3]) and won[0][4] >= settings.TRYON_QUALITY_BEST_OF_SKIP_SCORE
                if not skip_second:
                    await _progress_writer(session, job)(
                        "Drawing it a second way too, to keep whichever matches the products better"
                    )
                    second = await _attempt(engines[1])
                    attempts.append(second)
                    if not isinstance(second, BaseException):
                        won.append(second)

                if not won:
                    # both engines failed outright — raise whichever error
                    # is more informative, and let the handling below (which
                    # already knows how to fail a job and refund) take it
                    raise next(a for a in attempts if isinstance(a, BaseException))

                winner_name, winner_model, image, reports, _winner_score = max(won, key=lambda w: w[4])
                logger.info(
                    "tryon_best_of_chosen",
                    job_id=job.id,
                    scores={name: round(score, 1) for name, _, _, _, score in won},
                    winner=winner_name,
                )
                kept_image, ctype, kept = await _keep_person_if_on(job, image, "image/jpeg", layers, debug)
                await _complete_job(
                    session, job, kept_image, ctype, winner_name, winner_model,
                    placements=_placements(layers, reports),
                    drawn=[layer.name for layer in layers], face_kept=kept,
                )
                await _log_distractor_ranks(session, job, kept_image, layers, reports)
                return

            if provider.whole_outfit and not _quality_pipeline_on(provider):
                # one render with every item at once (shoes, bags, jewellery too)
                output = await provider.generate_outfit(model_url, _outfit_pieces(layers))
                image, ctype, kept = await _keep_person_if_on(job, output.image_bytes, output.content_type, layers, debug)
                await _complete_job(
                    session, job, image, ctype, provider.name, provider.model,
                    drawn=[layer.name for layer in layers], face_kept=kept,
                )
                return

            if provider.supports_masked_edit and _quality_pipeline_on(provider) and settings.TRYON_RENDER_ENGINE == "zoned":
                # each product's zone/layer/deformation read from its own
                # photo, large-region products first, small-region ones in
                # their own zoomed pass (see app/services/tryon_quality/zoned.py)
                person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
                image, reports = await render_zoned_look(
                    person,
                    [_look_item(layer) for layer in layers],
                    _pipeline_edit_masked_batch(provider),
                    retries=settings.TRYON_QUALITY_RETRIES,
                    min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
                    min_other=settings.TRYON_QUALITY_MIN_FIT,
                    budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
                    on_progress=_progress_writer(session, job),
                    debug=debug,
                )
                await _complete_job(
                    session, job, image, "image/jpeg", provider.name, provider.model,
                    placements=_placements(layers, reports),
                    drawn=[layer.name for layer in layers], face_kept=True,
                )
                await _log_distractor_ranks(session, job, image, layers, reports)
                return

            if provider.supports_masked_edit and _quality_pipeline_on(provider):
                # each product drawn through its own real edit mask — the
                # API itself refuses to touch anything outside it, not
                # reconstructed afterwards from a diff (see
                # app/services/tryon_quality/masked.py)
                person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
                image, reports = await render_masked_look(
                    person,
                    [_look_item(layer) for layer in layers],
                    _pipeline_edit_masked(provider),
                    retries=settings.TRYON_QUALITY_RETRIES,
                    min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
                    min_other=settings.TRYON_QUALITY_MIN_FIT,
                    budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
                    on_progress=_progress_writer(session, job),
                    debug=debug,
                )
                await _complete_job(
                    session, job, image, "image/jpeg", provider.name, provider.model,
                    placements=_placements(layers, reports),
                    drawn=[layer.name for layer in layers], face_kept=True,
                )
                await _log_distractor_ranks(session, job, image, layers, reports)
                return

            if provider.preserves_person and _quality_pipeline_on(provider):
                # the render used as it comes back, inspected and
                # corrected — no change detection, no mask, no merge
                person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
                try:
                    image, reports = await render_whole_look(
                        person,
                        [_look_item(layer) for layer in layers],
                        _pipeline_render_all(provider),
                        retries=settings.TRYON_QUALITY_RETRIES,
                        min_product=settings.TRYON_QUALITY_MIN_PRODUCT,
                        min_other=settings.TRYON_QUALITY_MIN_FIT,
                        budget_seconds=settings.TRYON_QUALITY_BUDGET_SECONDS,
                        on_progress=_progress_writer(session, job),
                        debug=debug,
                    )
                except QualityFailure as exc:
                    await _fail_job(
                        session,
                        job,
                        f"The render added {exc.item} beyond what you picked, so no result was returned and "
                        f"your credits were refunded. Found: {'; '.join(exc.issues[:3]) or 'an unrequested item'}. "
                        "Try again, or a different product photo.",
                        refund=True,
                    )
                    return
                kept_image, ctype, kept = await _keep_person_if_on(job, image, "image/jpeg", layers, debug)
                await _complete_job(
                    session, job, kept_image, ctype, provider.name, provider.model,
                    placements=_placements(layers, reports),
                    drawn=[layer.name for layer in layers], face_kept=kept,
                )
                await _log_distractor_ranks(session, job, kept_image, layers, reports)
                return

            if _quality_pipeline_on(provider):
                # render -> keep only the product -> inspect -> retry/refuse
                # (app/services/tryon_quality/pipeline.py)
                person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
                try:
                    image, reports = await render_look(
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
                        on_progress=_progress_writer(session, job),
                        debug=debug,
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
                    placements=_placements(layers, reports),
                    drawn=[layer.name for layer in layers], face_kept=True,
                )
                await _log_distractor_ranks(session, job, image, layers, reports)
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


async def _billed(job: TryOnJob) -> bool:  # noqa: ANN001
    return any((step or {}).get("provider_job_id") for step in (job.steps or []))


async def _run_direct_job(session, job: TryOnJob, provider: VirtualTryOnProvider, layers: list[_Layer]) -> None:  # noqa: ANN001
    """A look drawn one product at a time on the customer's own photo: one
    FASHN call per product, in order, each output stored as FASHN returned it
    and verified before the next product is drawn. Refused before any call if
    the look is over the limits. Once FASHN has accepted a product, a failure
    holds the job for review; it is never refunded or resubmitted."""
    try:
        if provider.model != "tryon-max":
            await _fail_job(session, job, "Direct try-on needs FASHN_MODEL=tryon-max.", refund=True)
            return
        if not layers or len(layers) > settings.TRYON_DIRECT_MAX_PRODUCTS:
            await _fail_job(session, job, "This look has no products, or more than the limit allows.", refund=True)
            return
        cost = credits_per_render(settings.FASHN_RESOLUTION, settings.FASHN_GENERATION_MODE)

        await _progress_writer(session, job)("Preparing your photo and products")
        try:
            person = await asyncio.to_thread(get_storage().read, job.user_photo.storage_key)
            products: list[ProductInput] = []
            for layer in layers:
                url = hires_product_url(_absolute_url(layer.image_url))
                image = await fetch_product_image(url)
                require_hires_product(image)
                products.append(ProductInput(name=layer.name, product_id=layer.product_id, image_url=url, image=image))
            check_plan(
                products,
                max_products=settings.TRYON_DIRECT_MAX_PRODUCTS,
                cost_per_render=cost,
                max_credits=settings.TRYON_DIRECT_MAX_FASHN_CREDITS,
            )
            available = await provider.credits_available()
            needed = cost * len(products)
            if needed > available:
                raise OrchestrationRefused(
                    f"this look needs {needed} FASHN credits ({len(products)} products x {cost}) "
                    f"but the current authorization allows {available}"
                )
        except OrchestrationRefused as exc:
            await _fail_job(session, job, f"We couldn't start this try-on: {exc}. Nothing was sent to FASHN.", refund=True)
            return
        except DirectInputError as exc:
            await _fail_job(session, job, f"We couldn't use the images for this try-on: {exc}.", refund=True)
            return

        storage = get_storage()
        input_keys: list[str] = []
        for product in products:
            mime = sniff_mime(product.image)
            input_keys.append(
                new_key("tryon", "direct-inputs", job.user_id, f"{job.id}-{len(input_keys)}.{mime.split('/')[-1]}")
            )
            storage.put(input_keys[-1], product.image, mime)  # type: ignore[arg-type]

        async def on_step(steps: list[dict]) -> None:
            for step in steps:
                step["input_key"] = input_keys[step["index"]]
            job.steps = [dict(step) for step in steps]
            sent = next((step for step in steps if step["status"] == "sent"), None)
            if sent is not None:
                job.progress = f"Drawing product {sent['index'] + 1} of {len(steps)}: {sent['name']}"[:160]
            recorded = [step["provider_job_id"] for step in steps if step.get("provider_job_id")]
            if recorded:
                job.provider_job_id = recorded[-1]
            await session.commit()

        async def on_raw(step: dict, data: bytes) -> None:
            key = new_key("tryon", "direct-steps", job.user_id, f"{job.id}-{step['index']}.png")
            storage.put(key, data, "image/png")
            step["raw_key"] = key

        async def render(image: bytes, product: ProductInput, on_submitted):  # noqa: ANN001
            return await provider.generate(
                TryOnInput(
                    model_image_url=to_data_uri(image),
                    garment_image_url=to_data_uri(product.image),
                    prompt=_only_this_product(product.name),
                    seed=settings.FASHN_SEED,
                ),
                on_submitted=on_submitted,
                purpose=f"direct:{job.id}:{product.product_id or product.name}"[:160],
            )

        try:
            sequence = await run_sequence(
                person, products, render=render, verify=verify_step, on_step=on_step, on_raw=on_raw
            )
        except TryOnProviderError as exc:
            if exc.provider_job_id:
                job.provider_job_id = exc.provider_job_id
            if await _billed(job):
                await _hold_failure(session, job, f"FASHN stopped the look: {exc}", steps=job.steps)
            else:
                await _fail_job(session, job, f"FASHN could not start this try-on: {exc}", refund=True)
            return

        if sequence.passed:
            await _progress_writer(session, job)("Checking every product in the final image")
            final = await final_check(
                person,
                sequence.image,
                sequence.outputs,
                [(step.get("qc") or {}).get("changed_bbox") for step in sequence.steps],
                [p.image for p in products],
                [p.name for p in products],
                with_vlm=settings.TRYON_DIRECT_VLM_QC and bool(settings.OPENAI_API_KEY),
            )
            for step, row in zip(sequence.steps, final["products"]):
                step["final_status"] = row["status"]
            if final["identity_ok"]:
                # the paid render is always delivered; each product is labelled
                # by what the checks could confirm, never claimed beyond that
                await _complete_sequence(session, job, provider, sequence, layers, cost, final)
            else:
                await _hold_final(session, job, provider, sequence, cost, final)
        else:
            failed = next(step for step in sequence.steps if step["status"] == "failed")
            await _hold_failure(
                session,
                job,
                f"We couldn't verify {failed['name']} on your photo, so this try-on was not delivered. "
                "Your credits are on hold while we review it.",
                steps=sequence.steps,
                reason=f"product {failed['index'] + 1} ({failed['name']}) failed verification: "
                + ", ".join(failed["failed_checks"]),
            )
    except Exception as exc:  # noqa: BLE001 — never strand a job as "processing"
        logger.error("tryon_direct_job_unexpected_error", job_id=job.id, error=str(exc))
        if await _billed(job):
            await _hold_failure(session, job, f"Unexpected error after FASHN accepted the try-on: {exc}", steps=job.steps)
        else:
            await _fail_job(session, job, f"Unexpected error: {exc}", refund=True)


_CHECK_WORDS = {
    "no_visible_edit": "the photo looks unchanged where this product should be",
    "low_product_colour_match": "the colour doesn't clearly match the product photo",
    "low_resolution": "the result image is small",
    "alignment_failed": "the result couldn't be lined up with your photo to compare",
    "face_check_inconclusive": "your face couldn't be found in both images to compare",
    "qc_failed": "the automatic check could not run",
    "qc_unreadable_image": "the automatic check could not read an image",
}


def _plain_reason(step: dict) -> str:
    words = [_CHECK_WORDS.get(c.removeprefix("identity:"), c) for c in step.get("failed_checks") or []]
    if step.get("final_status") not in (None, "verified"):
        words.append("a later product may have covered it")
    detail = "; ".join(dict.fromkeys(words)) or "it couldn't be confirmed"
    return f"Not confirmed automatically: {detail}. Check the photo."


def _only_this_product(name: str) -> str:
    """FASHN's prompt for one product. Live: a jhumka earrings photo that also
    showed long gold chains came back with a gold choker necklace the shopper
    never selected. Each call is told to add this product and nothing else."""
    extra = settings.TRYON_DIRECT_PROMPT.strip()
    base = (
        f"Put only this product on the person: {name[:120]}. "
        "Do not add any other jewelry, accessories or clothing that is not in the product image. "
        "Keep everything else on the person unchanged."
    )
    return f"{base} {extra}".strip()


def _confirmed(step: dict) -> bool:
    return bool(step.get("verified")) and step.get("final_status", "verified") == "verified"


async def _complete_sequence(session, job: TryOnJob, provider: VirtualTryOnProvider, sequence, layers: list[_Layer], cost: int, final: dict) -> None:  # noqa: ANN001
    """Every product verified: deliver the final FASHN output untouched."""
    output = sequence.output
    ext = "jpg" if output.content_type == "image/jpeg" else output.content_type.split("/")[-1]
    key = new_key("tryon", "results", job.user_id, f"{job.id}.{ext}")
    storage = get_storage()
    storage.put(key, sequence.image, output.content_type)
    with Image.open(io.BytesIO(sequence.image)) as img:
        width, height = img.size
    placements = [
        {
            "name": step["name"],
            "product_id": step["product_id"],
            "slot": (layer.slot or OutfitSlot.TOP).value,
            "image_url": step["image_url"],
            "drawn": _confirmed(step),
            "reason": None if _confirmed(step) else _plain_reason(step),
            "verification": "PASS" if _confirmed(step) else ("VERIFICATION_ERROR" if step.get("status") == "verification_error" else "REVIEW_REQUIRED"),
            "box": None,
        }
        for step, layer in zip(sequence.steps, layers)
    ]
    engine_meta = {
        **(output.meta or {}),
        "engine_mode": "direct",
        "provider": provider.name,
        "product_count": len(sequence.steps),
        "credits_per_render": cost,
        "sequence": [dict(step) for step in sequence.steps],
        "person_photo_id": job.user_photo_id,
        "person_input_size": [job.user_photo.width, job.user_photo.height],
        "job_started_at": job.started_at.isoformat() if job.started_at else None,
    }
    session.add(
        TryOnResult(
            job_id=job.id,
            storage_key=key,
            image_url=storage.signed_url(key),
            width=width,
            height=height,
            qc_report={
                "gate": {
                    "passed": all(_confirmed(step) for step in sequence.steps),
                    "failed_checks": sorted({c for step in sequence.steps for c in step.get("failed_checks") or []}),
                    "advisory": [],
                },
                "products": len(sequence.steps),
                "confirmed": sum(_confirmed(step) for step in sequence.steps),
                "final_check": final,
            },
            engine_meta=engine_meta,
            placements=placements,
        )
    )
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    job.provider = provider.name
    job.provider_model = provider.model
    job.provider_job_id = output.provider_job_id
    job.steps = [dict(step) for step in sequence.steps]
    session.add(
        AIUsage(
            user_id=job.user_id,
            kind=AIUsageKind.VIRTUAL_TRYON,
            provider=provider.name,
            model=provider.model,
            reference_type="tryon_job",
            reference_id=job.id,
            success=True,
        )
    )
    await session.commit()
    logger.info("tryon_job_completed", job_id=job.id, products=len(sequence.steps))


async def _hold_final(session, job: TryOnJob, provider: VirtualTryOnProvider, sequence, cost: int, final: dict) -> None:  # noqa: ANN001
    """Every product was drawn and verified when drawn, but the final image
    could not confirm all of them. The final FASHN output is stored for a
    reviewer, who may approve it; the customer is not told it succeeded."""
    output = sequence.output
    ext = "jpg" if output.content_type == "image/jpeg" else output.content_type.split("/")[-1]
    key = new_key("tryon", "results", job.user_id, f"{job.id}.{ext}")
    get_storage().put(key, sequence.image, output.content_type)
    with Image.open(io.BytesIO(sequence.image)) as img:
        width, height = img.size
    unconfirmed = [row["name"] for row in final["products"] if row["status"] != "verified"]
    reason = "final check could not confirm: " + (", ".join(unconfirmed) or "the person's identity")
    await _hold_failure(
        session,
        job,
        "We couldn't confirm every product in the final image, so it was not delivered. "
        "Your credits are on hold while we review it.",
        steps=sequence.steps,
        reason=reason,
    )
    job.review_payload = {
        "storage_key": key,
        "qc_report": {"gate": {"passed": False, "failed_checks": ["final_check"]}, "final_check": final},
        "engine_meta": {
            **(output.meta or {}),
            "engine_mode": "direct",
            "provider": provider.name,
            "product_count": len(sequence.steps),
            "credits_per_render": cost,
            "sequence": [dict(step) for step in sequence.steps],
        },
        "width": width,
        "height": height,
        "steps": job.steps,
    }
    await session.commit()


async def _hold_failure(session, job: TryOnJob, message: str, *, steps: list | None, reason: str | None = None) -> None:  # noqa: ANN001
    """FASHN has billed at least one product of this look. Nothing is delivered
    or refunded automatically; a reviewer decides. The stored steps show which
    products were drawn and which were not."""
    job.steps = [dict(step) for step in (steps or [])]
    job.status = JobStatus.FAILED
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = message
    job.provider = "fashn"
    job.provider_model = "tryon-max"
    job.review_state = "pending"
    job.review_reason = reason or message
    job.review_payload = {"storage_key": None, "steps": job.steps}
    session.add(
        AIUsage(
            user_id=job.user_id,
            kind=AIUsageKind.VIRTUAL_TRYON,
            provider="fashn",
            model="tryon-max",
            reference_type="tryon_job",
            reference_id=job.id,
            success=True,  # FASHN accepted and billed these products
        )
    )
    await session.commit()
    logger.warning("tryon_job_held_for_review", job_id=job.id, reason=job.review_reason)


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


def _reason_for(report: ItemReport) -> str | None:
    """A shopper-facing reason `drawn` is False — reusing the same
    history already kept for debugging, but as an answer to "where did
    my shoes go" rather than a log line. Distinguishes the two real
    cases: nothing on the photo answered to where the item goes at all
    (worth trying a clearer or different photo), versus the render
    itself failed (worth simply trying again — nothing wrong with the
    product or the photo)."""
    for line in report.history:
        if "couldn't find" in line:
            return "Couldn't find where this belongs on your photo — try a clearer or different photo."
        if "failed" in line:
            return "This item couldn't be rendered this time — try again."
    return "This item couldn't be applied — try again."


def _placements(layers: list[_Layer], reports: list[ItemReport]) -> list[dict]:
    """Where each item ended up, for the result view's labels.

    "drawn" is report.verified alone — never report.box by itself. A box
    says where a marker could point; it says nothing about whether the
    product actually passed inspection there. Trusting a box on its own
    used to mean an item that never passed a single retry could still be
    labelled "on photo" because some separate, independent lookup thought
    it spotted something similar. Only a verified item is still listed
    without a marker."""
    out: list[dict] = []
    for layer, report in zip(layers, reports):
        box = report.box if report.verified else None
        out.append(
            {
                "name": layer.name,
                "product_id": layer.product_id,
                "slot": (layer.slot or OutfitSlot.TOP).value,
                # the retailer's own photo of the thing. A card beside the
                # result shows the product the shopper is buying; a crop of
                # the render shows our rendering of it, which is a
                # different claim and a worse picture of a watch face.
                "image_url": layer.image_url,
                "drawn": report.verified,
                "reason": None if report.verified else _reason_for(report),
                "box": [round(box.x0, 4), round(box.y0, 4), round(box.x1, 4), round(box.y1, 4)] if box else None,
            }
        )
    return out


async def _distractors_for(session, product: Product, limit: int = 8) -> list[Product]:  # noqa: ANN001
    """The other active products in this one's own category — the catalog
    has no stored "this is the exact result set a search returned", so
    this is the closest always-available proxy for "the other results for
    the same query": the same category filter search_service.search_products
    itself would have applied."""
    if not product.category_id:
        return []
    rows = await session.execute(
        select(Product)
        .where(Product.is_active.is_(True), Product.category_id == product.category_id, Product.id != product.id)
        .options(selectinload(Product.images))
        .limit(limit)
    )
    return list(rows.scalars().all())


def _box_crop(image: np.ndarray, box) -> np.ndarray:  # noqa: ANN001
    h, w = image.shape[:2]
    x0, y0, x1, y1 = box.pixels(w, h)
    return image[y0:y1, x0:x1]


async def _distractor_images_for(session, job: TryOnJob, layer: _Layer) -> list:  # noqa: ANN001
    """The real "other options" the client showed at selection time, if it
    saved them (job.distractor_options, keyed by product_id) — the actual
    distractor set this check was designed around. Falls back to the
    same-category DB guess only when nothing was saved for this item (an
    older client, or a wardrobe item with no search behind it at all)."""
    saved = (job.distractor_options or {}).get(layer.product_id) if layer.product_id else None
    if saved:
        fetched = await asyncio.gather(
            *(_download(_absolute_url(o["image_url"])) for o in saved if o.get("image_url")),
            return_exceptions=True,
        )
        return [img for img in fetched if isinstance(img, np.ndarray)]

    product = (
        await session.get(Product, layer.product_id, options=[selectinload(Product.images)])
        if layer.product_id
        else None
    )
    if product is None:
        return []
    distractors = await _distractors_for(session, product)
    fetched = await asyncio.gather(
        *(_download(_absolute_url(p.primary_image_url)) for p in distractors if p.primary_image_url),
        return_exceptions=True,
    )
    return [img for img in fetched if isinstance(img, np.ndarray)]


async def _log_distractor_ranks(
    session, job: TryOnJob, image_bytes: bytes, layers: list[_Layer], reports: list[ItemReport]
) -> None:
    """Shadow mode (TRYON_RANK_DISTRACTORS): logs how the rendered result
    ranks the chosen product among its real distractors (or a same-category
    guess — see _distractor_images_for), by CLIP embedding similarity —
    never raises, never affects the job or the result. See
    distractor_rank.py."""
    if not settings.TRYON_RANK_DISTRACTORS:
        return
    try:
        full = decode(image_bytes)
        for layer, report in zip(layers, reports):
            if not report.verified or report.box is None or layer.product_id is None:
                continue
            distractor_images = await _distractor_images_for(session, job, layer)
            if not distractor_images:
                continue
            crop = _box_crop(full, report.box)
            product_image = await _download(_absolute_url(layer.image_url))
            result = rank_against_distractors(crop, product_image, distractor_images)
            log_distractor_rank(job.id, layer.name, result)
    except Exception as exc:  # noqa: BLE001 — a shadow-mode signal must never affect a real job
        logger.warning("tryon_distractor_rank_failed", job_id=job.id, error=str(exc)[:200])


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
    placements: list[dict] | None = None,
) -> None:
    if not face_kept:  # the quality pipeline already kept the person's own face
        image_bytes, content_type = await _with_original_face(job, image_bytes, content_type, list(drawn))
    ext = "jpg" if content_type == "image/jpeg" else content_type.split("/")[-1]
    key = new_key("tryon", "results", job.user_id, f"{job.id}.{ext}")
    storage = get_storage()
    storage.put(key, image_bytes, content_type)
    url = storage.signed_url(key)

    session.add(TryOnResult(job_id=job.id, storage_key=key, image_url=url, placements=placements))
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
