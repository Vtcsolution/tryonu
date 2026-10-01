"""The zoned pipeline (TRYON_RENDER_ENGINE=zoned).

Each product's zone, draw layer and how it deforms on a body come from
its own photo (zone_spec.py), never its title — the universal rule this
pipeline exists to enforce structurally, not just follow by convention.

Staging: large-region products (a garment covering most of the body) draw
first, up to 3 per call; every small-region product (jewellery, a watch,
a bag, eyewear) then gets its own ZOOMED pass — cropped tight around its
own zone so the model sees it many times larger, the same technique
pipeline.py's `_render_close_up` already validated for a single item,
generalised here to a batch of up to 2-3 non-overlapping small items
sharing one crop.

A batch is a real reduction in paid image-generation calls, not just
shared concurrency: every item in a batch is drawn in ONE
edit_masked_batch() call, against a mask with one disjoint transparent
window per item (see app/ai/providers/openai_image.py's
masked_prompt_batch/edit_masked_batch, additive — masked.py's own
single-item edit_masked() is untouched and still what "auto" mode uses).
The real cost of that: the mask can't label which window is whose, so the
model has to infer correspondence from each product's own described
position — a batch of 3 is cheaper per call, never free, and riskier on
placement than a single clean window. Verification (judge() per item,
individually, against its own region in the shared result) is what
catches a mistake there rather than trusting the batch blindly: an item
that fails stays in the batch and is retried together with its
still-failing siblings, never redrawing one that already passed.

Pixel-lock: `current` never leaves the base photo's own fixed resolution.
Every pass's own raw output — whatever size the model actually returns —
is resized DOWN (or up) to match the exact pixel box it is being pasted
into on `current`'s fixed grid, never the reverse. masked.py's multi-item
path instead upscales the *shared canvas* to the model's own output
resolution when several items share a round; this pipeline makes the
opposite trade deliberately, so the untouched majority of the photo —
face, skin, body, background — is never resampled at all, however many
passes the look takes.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import cv2
import numpy as np

from app.core.logging import logger
from app.services.face_restore import detect_face
from app.services.tryon_quality.compose import Region, decode, encode_jpeg
from app.services.tryon_quality.debug_capture import DebugCapture
from app.services.tryon_quality.judge import judge
from app.services.tryon_quality.locate import find_body_part
from app.services.tryon_quality.masked import encode_png
from app.services.tryon_quality.pipeline import (
    ItemReport,
    LookItem,
    ProgressFn,
    _cap,
    _download,
    _for_model,
    _say,
)
from app.services.tryon_quality.product_prep import describe_product
from app.services.tryon_quality.zone_spec import ZoneSpec, zone_spec_for


@dataclass(frozen=True, slots=True)
class BatchPiece:
    """One product inside a batched edit call — see
    app/ai/providers/base.py's edit_masked_batch()."""

    item: LookItem
    description: str
    fix: str = ""
    detail: bool = False


BatchMaskedRenderFn = Callable[[bytes, bytes, list[BatchPiece]], Awaitable[bytes]]

# ----------------------------------------------------------- zone geometry
#
# The same face-relative windows masked.py already validated live, keyed
# by zone (from the product's own photo) instead of OutfitSlot/name.

_LARGE_REGION = {
    "full_body": Region(0.03, 0.0, 0.97, 0.97),
    "torso": Region(0.03, 0.0, 0.97, 0.75),
    "outerwear": Region(0.0, 0.0, 1.0, 0.8),
    "lower_body": Region(0.05, 0.4, 0.95, 0.97),
}
_NECKLINE_DROP = 0.35
_GARMENT_HALF_WIDTH = 2.6

_EYE_TOP, _EYE_BOTTOM, _EYEWEAR_HALF_WIDTH = 0.15, 0.75, 0.75
_TIKKA_TOP, _TIKKA_BOTTOM, _TIKKA_HALF_WIDTH = -0.2, 0.3, 0.35
_EAR_TOP, _EAR_BOTTOM, _EAR_HALF_WIDTH = 0.15, 0.95, 0.85
_SHOULDER_DROP = 1.15
_HAND_ITEM_MAX_WIDTH, _HAND_ITEM_MAX_HEIGHT = 2.5, 2.0

_BODY_PART_FOR_ZONE = {
    "hand_wrist": "the person's hands and wrists",
    "neck_chest": "the person's neck, shoulders and upper chest",
    "bag": "where a bag would be carried: the person's hand, shoulder or side",
    "feet": "the person's feet and the shoes or footwear area",
    "other": "where this item would naturally be worn or carried on the person",
}


def _face_window(face, base: np.ndarray, top_frac: float, bottom_frac: float, half_width_frac: float) -> Region:  # noqa: ANN001
    h, w = base.shape[:2]
    cx = (face.x + face.w / 2) / w
    half = half_width_frac * face.w / w
    top = max(0.0, (face.y + top_frac * face.h) / h)
    bottom = min(1.0, (face.y + bottom_frac * face.h) / h)
    return Region(max(0.0, cx - half), top, min(1.0, cx + half), bottom)


def _large_region(zone: str, face, base: np.ndarray) -> Region:  # noqa: ANN001
    region = _LARGE_REGION.get(zone, _LARGE_REGION["full_body"])
    if face is None:
        return region
    h, w = base.shape[:2]
    top = min(region.y1, (face.y + face.h + _NECKLINE_DROP * face.h) / h)
    cx = (face.x + face.w / 2) / w
    half = _GARMENT_HALF_WIDTH * face.w / w
    x0 = max(region.x0, cx - half)
    x1 = min(region.x1, cx + half)
    return Region(x0, top, x1, region.y1)


async def _small_region(zone: str, face, base: np.ndarray) -> Region | None:  # noqa: ANN001
    if face is not None and zone == "eyewear":
        return _face_window(face, base, _EYE_TOP, _EYE_BOTTOM, _EYEWEAR_HALF_WIDTH)
    if face is not None and zone == "forehead":
        return _face_window(face, base, _TIKKA_TOP, _TIKKA_BOTTOM, _TIKKA_HALF_WIDTH)
    if face is not None and zone == "ears":
        return _face_window(face, base, _EAR_TOP, _EAR_BOTTOM, _EAR_HALF_WIDTH)
    if face is not None and zone == "head_other":
        return _face_window(face, base, -0.4, 0.6, 1.4)

    part = _BODY_PART_FOR_ZONE.get(zone, _BODY_PART_FOR_ZONE["other"])
    try:
        region = await find_body_part(base, part)
    except Exception as exc:  # noqa: BLE001 — no lookup available is not a crash
        logger.warning("tryon_zoned_locate_failed", zone=zone, error=str(exc)[:200])
        region = None
    if region is None or face is None:
        return region
    if zone in {"hand_wrist", "bag"}:
        h, w = base.shape[:2]
        shoulder = min(1.0, (face.y + face.h * _SHOULDER_DROP) / h)
        if region.y0 < shoulder:
            region = Region(region.x0, shoulder, region.x1, max(region.y1, shoulder + 0.05))
        max_w, max_h = _HAND_ITEM_MAX_WIDTH * face.w / w, _HAND_ITEM_MAX_HEIGHT * face.h / h
        width, height = region.x1 - region.x0, region.y1 - region.y0
        if width > max_w or height > max_h:
            cx, cy = (region.x0 + region.x1) / 2, (region.y0 + region.y1) / 2
            half_w, half_h = min(width, max_w) / 2, min(height, max_h) / 2
            region = Region(
                max(0.0, cx - half_w), max(0.0, cy - half_h), min(1.0, cx + half_w), min(1.0, cy + half_h)
            )
    return region


async def _zone_region(spec: ZoneSpec, face, base: np.ndarray) -> Region | None:  # noqa: ANN001
    if spec.large_region:
        return _large_region(spec.zone, face, base)
    return await _small_region(spec.zone, face, base)


def _overlaps(a: Region, b: Region, margin: float = 0.02) -> bool:
    return not (a.x1 + margin <= b.x0 or b.x1 + margin <= a.x0 or a.y1 + margin <= b.y0 or b.y1 + margin <= a.y0)


def _batches(indices: list[int], regions: list[Region], max_size: int) -> list[list[int]]:
    """Group indices whose windows don't overlap, up to max_size per
    group — the same non-overlap safety masked.py's _waves() already
    relies on, with an explicit hard cap instead of an unbounded one."""
    batches: list[list[int]] = []
    for i in indices:
        for batch in batches:
            if len(batch) >= max_size:
                continue
            if not any(_overlaps(regions[i], regions[j]) for j in batch):
                batch.append(i)
                break
        else:
            batches.append([i])
    return batches


_LARGE_BATCH_MAX = 3
_SMALL_BATCH_MAX = 3  # "2-3 products per call"


def _mask_png_multi(shape: tuple[int, int], regions: list[Region]) -> bytes:
    """One opaque PNG with one disjoint transparent window per region —
    OpenAI's edit mask format: transparent = editable."""
    h, w = shape
    alpha = np.full((h, w), 255, np.uint8)
    for region in regions:
        x0, y0, x1, y1 = region.pixels(w, h)
        alpha[y0:y1, x0:x1] = 0
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = alpha
    ok, buf = cv2.imencode(".png", rgba)
    if not ok:
        raise ValueError("could not encode mask")
    return buf.tobytes()


_FEATHER_MARGIN = 0.02


def _paste(base: np.ndarray, raw: np.ndarray, region: Region) -> np.ndarray:
    """`raw` resized to `base`'s own resolution first — pixel-lock means
    the canvas never changes size to match a pass's output, only the
    output is ever resampled to fit the canvas it is being pasted onto."""
    h, w = base.shape[:2]
    if raw.shape[:2] != (h, w):
        raw = cv2.resize(raw, (w, h), interpolation=cv2.INTER_LANCZOS4)
    x0, y0, x1, y1 = region.pixels(w, h)
    mask = np.zeros((h, w), dtype=np.float32)
    mask[y0:y1, x0:x1] = 1.0
    feather = max(3, int(_FEATHER_MARGIN * min(h, w)))
    mask = cv2.GaussianBlur(mask, (feather * 2 + 1, feather * 2 + 1), 0)
    m = mask[..., None]
    return (raw.astype(np.float32) * m + base.astype(np.float32) * (1 - m)).astype(np.uint8)


async def _execute_batch_pass(
    batch: list[int],
    items: list[LookItem],
    products: list[np.ndarray],
    descriptions: list[str],
    regions: list[Region],
    canvas: np.ndarray,
    reports: list[ItemReport],
    edit_batch: BatchMaskedRenderFn,
    *,
    small_item: bool,
    min_p: float,
    min_other: float,
    retries: int,
    budget_seconds: int,
    started: float,
    debug: DebugCapture | None,
) -> np.ndarray:
    """ONE batched edit call per round against `canvas`. Every item that
    passes (or is a near miss, or has run out of attempts/budget) drops
    out; everything still failing is retried TOGETHER in the next round's
    own single call — never a solo call per failed item, and never a
    redraw of a sibling that already passed."""
    pending = list(batch)
    fixes = {i: "" for i in batch}
    accepted: dict[int, np.ndarray] = {}
    for attempt in range(retries + 1):
        if not pending:
            break
        for_model = _for_model(canvas)
        mask_png = _mask_png_multi(for_model.shape[:2], [regions[i] for i in pending])
        if debug is not None:
            debug.save("mask", mask_png, label="_".join(items[i].name[:20] for i in pending))
        pieces = [BatchPiece(items[i], descriptions[i], fixes[i], attempt > 0) for i in pending]
        try:
            raw_bytes = await edit_batch(encode_png(for_model), mask_png, pieces)
        except Exception as exc:  # noqa: BLE001 — one batch's failure must not lose the rest of the look
            logger.warning("tryon_zoned_batch_edit_failed", items=[items[i].name[:40] for i in pending], error=str(exc)[:200])
            for i in pending:
                reports[i].history.append(f"attempt {attempt + 1}: the render failed ({str(exc)[:120]})")
            if attempt >= retries or time.monotonic() - started > budget_seconds:
                break
            continue
        raw = decode(raw_bytes)
        if debug is not None:
            debug.save("provider_output", raw_bytes, label="_".join(items[i].name[:20] for i in pending))
        judged = raw if raw.shape[:2] == canvas.shape[:2] else cv2.resize(
            raw, (canvas.shape[1], canvas.shape[0]), interpolation=cv2.INTER_LANCZOS4
        )
        still_pending = []
        last_chance = attempt >= retries or time.monotonic() - started > budget_seconds
        for i in pending:
            verdict = await judge(products[i], canvas, judged, regions[i], descriptions[i], small_item, items[i].image_url)
            reports[i].attempts = attempt + 1
            reports[i].history.append(
                f"attempt {attempt + 1}: product={verdict.product_match:.0f} "
                f"worn={verdict.worn_correctly:.0f} realism={verdict.realism:.0f}"
            )
            passed = verdict.passes(min_p, min_other)
            close = verdict.passes(min_p - 1, min_other - 1)
            if passed or close or last_chance:
                if not passed:
                    reports[i].history.append("kept as a near miss rather than spending a redraw" if close else "out of time for another attempt")
                reports[i].verdict = verdict
                reports[i].box = regions[i]
                reports[i].verified = passed or close
                accepted[i] = judged
            else:
                fixes[i] = "; ".join(verdict.issues[:3])
                still_pending.append(i)
        pending = still_pending

    merged = canvas
    for i, judged_img in accepted.items():
        merged = _paste(merged, judged_img, regions[i])
    return merged


async def _run_small_batch(
    batch: list[int],
    items: list[LookItem],
    products: list[np.ndarray],
    descriptions: list[str],
    regions: list[Region],
    reports: list[ItemReport],
    current: np.ndarray,
    edit_batch: BatchMaskedRenderFn,
    *,
    min_product: float,
    min_other: float,
    retries: int,
    budget_seconds: int,
    started: float,
    debug: DebugCapture | None,
) -> np.ndarray:
    """A zoomed pass: crop `current` around the union of this batch's own
    zones, render against that crop (so each item appears many times
    larger than it would in the whole photo — pipeline.py's
    _render_close_up technique, generalised to a shared crop), then
    resize the result back down to the crop's own pixel box and paste —
    pixel-lock holds even inside a zoom."""
    h, w = current.shape[:2]
    boxes = [regions[i].pixels(w, h) for i in batch]
    x0 = max(0, min(b[0] for b in boxes))
    y0 = max(0, min(b[1] for b in boxes))
    x1 = min(w, max(b[2] for b in boxes))
    y1 = min(h, max(b[3] for b in boxes))
    bw, bh = x1 - x0, y1 - y0
    side = max(3.0 * max(bw, bh), 0.12 * min(h, w))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cx0, cy0 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
    cx1, cy1 = int(min(w, cx + side / 2)), int(min(h, cy + side / 2))
    crop = current[cy0:cy1, cx0:cx1]
    ch, cw = crop.shape[:2]
    up = 1024 / max(ch, cw)
    zoomed = cv2.resize(crop, (round(cw * up), round(ch * up)), interpolation=cv2.INTER_LANCZOS4) if up > 1 else crop

    def _local(region: Region) -> Region:
        # Fractions are resolution-independent, so this is correct whether
        # or not `zoomed` is an upscale of `crop` — relative to the crop's
        # own box is all that matters.
        px0, py0, px1, py1 = region.pixels(w, h)
        return Region(
            max(0.0, (px0 - cx0) / cw),
            max(0.0, (py0 - cy0) / ch),
            min(1.0, (px1 - cx0) / cw),
            min(1.0, (py1 - cy0) / ch),
        )

    local_regions = list(regions)
    for i in batch:
        local_regions[i] = _local(regions[i])

    merged_zoom = await _execute_batch_pass(
        batch, items, products, descriptions, local_regions, zoomed, reports, edit_batch,
        small_item=True, min_p=min_product, min_other=min_other, retries=retries,
        budget_seconds=budget_seconds, started=started, debug=debug,
    )
    merged_crop = (
        cv2.resize(merged_zoom, (cw, ch), interpolation=cv2.INTER_AREA)
        if merged_zoom.shape[:2] != (ch, cw)
        else merged_zoom
    )
    # Re-derive each accepted item's report.box in full-photo fractions —
    # it was set above in the crop's own local fractions.
    for i in batch:
        local_box = reports[i].box
        if local_box is None or not reports[i].verified:
            continue
        px0, py0, px1, py1 = local_box.pixels(cw, ch)
        reports[i].box = Region((cx0 + px0) / w, (cy0 + py0) / h, (cx0 + px1) / w, (cy0 + py1) / h)
    full = current.copy()
    full[cy0:cy1, cx0:cx1] = merged_crop
    return full


async def render_zoned_look(
    person: bytes,
    items: list[LookItem],
    edit_batch: BatchMaskedRenderFn,
    *,
    retries: int = 1,
    min_product: float = 7.0,
    min_other: float = 6.0,
    budget_seconds: int = 60,
    on_progress: ProgressFn | None = None,
    debug: DebugCapture | None = None,
) -> tuple[bytes, list[ItemReport]]:
    """Large-region products first (max 3 per call), then every
    small-region product in its own zoomed pass (max 2-3 per call).
    `current` stays at the base photo's own fixed resolution throughout —
    see the module docstring's pixel-lock rule. Works for any number of
    products: more products simply means more small-region passes."""
    started = time.monotonic()
    current = _cap(decode(person))
    if debug is not None:
        debug.save("input", current)
    face = detect_face(current)
    reports = [ItemReport(name=item.name) for item in items]

    products = await asyncio.gather(*(_download(item.image_url) for item in items))
    specs = await asyncio.gather(*(zone_spec_for(p, item.image_url) for p, item in zip(products, items)))
    descriptions = await asyncio.gather(
        *(describe_product(p, item.image_url, item.name) for p, item in zip(products, items))
    )
    for item, spec in zip(items, specs):
        logger.info(
            "tryon_zoned_spec", item=item.name[:60], zone=spec.zone, layer=spec.layer,
            large_region=spec.large_region, deformation=spec.deformation,
        )

    regions: list[Region | None] = list(await asyncio.gather(*(_zone_region(spec, face, current) for spec in specs)))
    for i, region in enumerate(regions):
        if region is None:
            reports[i].history.append("couldn't find where this goes on the photo")

    ready = [i for i, r in enumerate(regions) if r is not None]
    large = sorted((i for i in ready if specs[i].large_region), key=lambda i: specs[i].layer)
    small = sorted((i for i in ready if not specs[i].large_region), key=lambda i: specs[i].layer)

    for batch in _batches(large, regions, _LARGE_BATCH_MAX):
        names = ", ".join(items[i].name[:30] for i in batch)
        await _say(on_progress, f"Drawing {names}")
        current = await _execute_batch_pass(
            batch, items, products, descriptions, regions, current, reports, edit_batch,
            small_item=False, min_p=min_product, min_other=min_other, retries=retries,
            budget_seconds=budget_seconds, started=started, debug=debug,
        )
        if debug is not None:
            debug.save("after_paste", current, label=f"large_{'_'.join(str(i) for i in batch)}")

    for batch in _batches(small, regions, _SMALL_BATCH_MAX):
        names = ", ".join(items[i].name[:30] for i in batch)
        await _say(on_progress, f"Drawing {names}")
        current = await _run_small_batch(
            batch, items, products, descriptions, regions, reports, current, edit_batch,
            min_product=min_product, min_other=min_other, retries=retries,
            budget_seconds=budget_seconds, started=started, debug=debug,
        )
        if debug is not None:
            debug.save("after_paste", current, label=f"small_{'_'.join(str(i) for i in batch)}")

    return encode_jpeg(current, 97), reports
