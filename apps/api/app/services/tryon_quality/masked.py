"""Try-on via real, API-level masked editing — each product drawn only
into a transparent window of an edit mask, with everywhere else on the
photo protected by the API itself.

Why this exists, next to render_look/render_whole_look: those two exist
because most engines don't give the person back unchanged, and each
copes with that in its own way — render_look reconstructs protection
afterwards, by finding what an unconstrained whole-look redraw changed
and merging only the parts judged to be the product; render_whole_look
trusts an engine that mostly preserves the person on its own. Both are
working around the same fact: the model was free to touch every pixel,
and something downstream has to decide, after it already has, which of
what it touched was allowed.

A real edit mask removes the question. The API is told which pixels it
may draw into (an alpha channel, not a sentence), and every other pixel
is refused before generation starts — not reconstructed, not trusted,
refused. Measured live, three chained edits (a shalwar kameez, a watch,
a handbag) on the same photo: 2-4% of the untouched region differed from
the original per edit — re-encoding noise, not redrawing — against
27-40% for an engine that "mostly" preserves the person and far more for
one given no protection at all. It is also structurally simpler: no
alignment, no diff, no candidate blobs, no vision call to decide whose
blob is whose — which is exactly the machinery every seam, ghost,
fragmented-limb and half-original-photo bug this project has chased came
from.

The trade-off is real and stated plainly: two products can only share a
round if their windows don't overlap — a dress's mask covers most of the
body, so it and a watch cannot be drawn in the same pass without each
ignoring the other's change, and must go one after another — where the
whole-look engines draw everything in one call regardless. What overlap
actually forces to wait is worked out per look, not assumed from the
item count: a watch on one wrist and a bag in the other usually don't
touch, and draw in the same round; a dress and anything on the torso
almost always do. See _waves() below.

Where the region to protect comes FROM is the one place this still
depends on a guess rather than a guarantee, and the one place a mistake
here is expensive rather than merely imprecise: whatever is inside the
window is not just "probably the product" the way a merge's chosen blob
was, it is the ONLY thing the model is allowed to touch. A garment's
mask is a generous, face-relative rectangle (see _MASK_REGION below),
not real body segmentation, because building the latter is its own,
separate problem. A small worn item's mask reuses the body-part lookup
the older pipeline already relies on (pipeline._area_for) — a live
vision call, and not a perfectly reliable one: asked live for "the
person's hands, forearms and shoulders" it once returned a box starting
2.5% down the photo, the top of her head, and the bag edit drew a scarf
into it, over her face. _mask_region's own clamp (below) is the
backstop for exactly that: nothing routed through the vision lookup is
ever allowed to reach above the shoulder, whatever the lookup says.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable

import cv2
import numpy as np

from app.core.logging import logger
from app.models.enums import OutfitSlot
from app.services.face_restore import detect_face
from app.services.outfit_slots import worn_on_head
from app.services.tryon_quality.compose import Region, decode, encode_jpeg
from app.services.tryon_quality.judge import judge
from app.services.tryon_quality.pipeline import (
    ItemReport,
    LookItem,
    ProgressFn,
    RenderHint,
    _AROUND_THE_NECK,
    _area_for,
    _cap,
    _download,
    _for_model,
    _GARMENTS,
    _min_product_for,
    _ON_THE_FLOOR,
    _say,
    _SMALL,
)
from app.services.tryon_quality.product_prep import describe_product

# A garment's mask, face-relative fractions of the photo: generous on
# purpose. Too small clips the garment against a hard edge it cannot
# cross; too large only widens the area the model is trusted to blend
# naturally into, which is the one thing it is reliably good at. Live,
# 0.05-0.95 wide and down to the ankle for anything with a lower half
# drew full sleeves and hemlines with room to spare and never touched
# the face or the floor.
_MASK_REGION = {
    OutfitSlot.DRESS: Region(0.03, 0.0, 0.97, 0.97),
    OutfitSlot.TOP: Region(0.03, 0.0, 0.97, 0.75),
    OutfitSlot.OUTERWEAR: Region(0.0, 0.0, 1.0, 0.8),
    OutfitSlot.BOTTOM: Region(0.05, 0.4, 0.95, 0.97),
}
# top of the mask starts just under the chin, not at the collar — a
# high neckline or a dupatta thrown back needs the collarbone in reach
_NECKLINE_DROP = 0.35  # of a face-height, below the bottom of the face
# A garment's mask never reaches wider than this, either side of her own
# centre. _MASK_REGION's fixed 0.03-0.97 is the ceiling for someone who
# already fills most of the frame; most photos aren't that tight a crop,
# and everything between her and that edge — wall, pillars, a wedding
# hall's own décor — was sitting inside the "editable" window right along
# with the sleeve. Live, on a full-body photo where she filled under half
# the frame width: the room behind her came back completely re-staged,
# a different hall than the one she was standing in, while the garment
# itself rendered correctly — the mask, not the model, was the bug. 2.6
# face-widths each side is generous enough for a dupatta thrown open or
# a flared sleeve (checked live against the same photo, hem to cuff,
# nothing clipped) without also handing over everything beside her.
_GARMENT_HALF_WIDTH = 2.6  # face-widths, each side of her centre
# the lowest a hand/wrist/bag item's own window may start: below this,
# never above it, regardless of what the body-part lookup returned
_SHOULDER_DROP = 1.15  # of a face-height, below the bottom of the face

# Sunglasses, glasses, goggles: no clamp protected these at all — every
# other worn-on-head item (a hat, an earring, a hijab) is exempted from
# _SHOULDER_DROP because it legitimately needs to reach the head, so
# eyewear inherited open trust in whatever the vision lookup answered
# with nothing checking it. Live, on a real photo: asked for where
# oversized sunglasses go, it returned a window nearly 3 face-widths
# wide and 2 face-heights tall, reaching from above the eyebrows to
# below the chin — most of the face, not a band across the eyes — and
# the render came back with a different bone structure, closer to the
# product photo's own model than the customer's. Unlike a bag or a
# watch, eyewear's real position is not something a body-part lookup
# needs to guess: it sits on the face, at a fixed place relative to it,
# every time. So this skips the vision call entirely, the same way a
# garment's mask does, rather than clamping a number that keeps coming
# back wrong.
_EYEWEAR = re.compile(r"\b(sunglasses|glasses|eyeglasses|spectacles|goggles)\b")
_EYE_TOP = 0.15  # face-heights below the top of the face: just above the brow
_EYE_BOTTOM = 0.75  # face-heights below the top of the face: upper cheek, well short of the mouth
_EYEWEAR_HALF_WIDTH = 0.75  # face-widths each side of centre: room for temples on an oversized frame

# drawn first to last: a sleeve has to exist before a bracelet can sit on
# top of the wrist inside it, and a bag is carried over a finished outfit
_MASK_ORDER = {
    OutfitSlot.DRESS: 0,
    OutfitSlot.BOTTOM: 1,
    OutfitSlot.TOP: 2,
    OutfitSlot.OUTERWEAR: 3,
    OutfitSlot.SHOES: 4,
    OutfitSlot.BAG: 5,
}
_LAST = 6  # watch, jewellery, anything else: on top of everything already drawn

MaskedRenderFn = Callable[[bytes, bytes, LookItem, RenderHint], Awaitable[bytes]]


async def _mask_region(item: LookItem, face, base: np.ndarray) -> Region | None:  # noqa: ANN001
    """Where to cut this item's transparent window."""
    if item.slot in _GARMENTS:
        region = _MASK_REGION.get(item.slot)
        if region is None or face is None:
            return region
        h, w = base.shape[:2]
        top = min(region.y1, (face.y + face.h + _NECKLINE_DROP * face.h) / h)
        # Narrow the slot's own fixed width toward her, never widen it —
        # a close-up photo where the face-relative window would exceed
        # the fixed bounds just keeps those bounds unchanged.
        cx = (face.x + face.w / 2) / w
        half = _GARMENT_HALF_WIDTH * face.w / w
        x0 = max(region.x0, cx - half)
        x1 = min(region.x1, cx + half)
        return Region(x0, top, x1, region.y1)

    name = item.name.lower()
    if face is not None and _EYEWEAR.search(name):
        h, w = base.shape[:2]
        cx = (face.x + face.w / 2) / w
        half = _EYEWEAR_HALF_WIDTH * face.w / w
        top = (face.y + _EYE_TOP * face.h) / h
        bottom = (face.y + _EYE_BOTTOM * face.h) / h
        return Region(max(0.0, cx - half), top, min(1.0, cx + half), bottom)

    region = await _area_for(item, face, base)
    if region is None or face is None:
        return region
    if worn_on_head(name) or _AROUND_THE_NECK.search(name) or item.slot in _ON_THE_FLOOR:
        return region  # legitimately near the head, the neck, or nowhere near either

    # A bag, a watch, a ring, a bracelet: none of them belong above the
    # shoulder, whatever the body-part lookup just said. Asked live for
    # "the person's hands, forearms and shoulders", it returned a box
    # starting 2.5% down the photo — the top of her head — on one run,
    # and a sensible one at shoulder height on the next: the same query,
    # two very different answers. This is the backstop for whichever one
    # it gives.
    shoulder = min(1.0, (face.y + face.h * _SHOULDER_DROP) / base.shape[0])
    if region.y0 < shoulder:
        return Region(region.x0, shoulder, region.x1, max(region.y1, shoulder + 0.05))
    return region


def _mask_png(shape: tuple[int, int], region: Region) -> bytes:
    """A same-size, fully opaque PNG except for a transparent window at
    `region` — OpenAI's edit mask format: transparent = editable."""
    h, w = shape
    alpha = np.full((h, w), 255, np.uint8)
    x0, y0, x1, y1 = region.pixels(w, h)
    alpha[y0:y1, x0:x1] = 0
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = alpha
    ok, buf = cv2.imencode(".png", rgba)
    if not ok:
        raise ValueError("could not encode mask")
    return buf.tobytes()


def _order_of(items: list[LookItem]) -> list[int]:
    return sorted(range(len(items)), key=lambda i: (_MASK_ORDER.get(items[i].slot, _LAST), i))


def _overlaps(a: Region, b: Region, margin: float = 0.02) -> bool:
    """Would two mask windows touch or cross, with a small buffer so a
    seam right at the boundary (the API's own blend, not ours) never has
    to be discovered live to be believed?"""
    return not (a.x1 + margin <= b.x0 or b.x1 + margin <= a.x0 or a.y1 + margin <= b.y0 or b.y1 + margin <= a.y0)


def _waves(ready: list[int], regions: list[Region | None]) -> list[list[int]]:
    """Batch draw steps whose windows don't overlap so independent items —
    a watch on one wrist, a bag in the other hand — render in the same API
    round instead of waiting their turn, while anything whose window
    crosses an earlier one still waits for it. `ready` already comes in
    draw-priority order (garments first, then worn items), so a later item
    that collides with an earlier one always yields the earlier a wave to
    itself rather than the reverse."""
    waves: list[list[int]] = []
    for step in ready:
        region = regions[step]
        for wave in waves:
            if not any(_overlaps(region, regions[s]) for s in wave):
                wave.append(step)
                break
        else:
            waves.append([step])
    return waves


async def _render_item(
    item: LookItem,
    product: np.ndarray,
    description: str,
    region: Region,
    canvas: np.ndarray,
    report: ItemReport,
    edit: MaskedRenderFn,
    *,
    min_p: float,
    min_other: float,
    retries: int,
    budget_seconds: int,
    started: float,
) -> np.ndarray | None:
    """One item's own retry loop, against a shared starting canvas it does
    not mutate — a sibling drawn the same round reads the same pixels.
    Returns the accepted render, or None if every attempt failed outright."""
    note = ""
    for_model = _for_model(canvas)
    mask_png = _mask_png(for_model.shape[:2], region)
    for attempt in range(retries + 1):
        hint = RenderHint(description=description, fix=note)
        try:
            raw_bytes = await edit(encode_png(for_model), mask_png, item, hint)
        except Exception as exc:  # noqa: BLE001 — one item's failure must not lose the rest
            logger.warning("tryon_masked_edit_failed", item=item.name[:60], error=str(exc)[:200])
            report.history.append(f"attempt {attempt + 1}: the render failed ({str(exc)[:120]})")
            return None
        # Used as it comes back, at the model's own output resolution —
        # sharper than the small input it was given (see MODEL_SIDE's own
        # comment) — never shrunk to match what was sent, the same way
        # render_whole_look never shrinks Gemini's output.
        raw = decode(raw_bytes)

        verdict = await judge(product, canvas, raw, region, description, item.slot in _SMALL)
        report.attempts = attempt + 1
        report.history.append(
            f"attempt {attempt + 1}: product={verdict.product_match:.0f} "
            f"worn={verdict.worn_correctly:.0f} realism={verdict.realism:.0f}"
        )
        passed = verdict.passes(min_p, min_other)
        # A near miss is kept as it is — "product 6 instead of 7" is a
        # detail nobody sees, and redrawing costs the customer's own
        # minute (see TRYON_QUALITY_BUDGET_SECONDS). Out of budget, the
        # best attempt made ships rather than nothing.
        close = verdict.passes(min_p - 1, min_other - 1)
        # last_chance: either this was the final retry, or the customer's
        # own time budget for the whole look is spent — either way, this
        # attempt ships rather than nothing.
        last_chance = attempt >= retries or time.monotonic() - started > budget_seconds
        if passed or close or last_chance:
            if not passed:
                report.history.append("kept as a near miss rather than spending a redraw" if close else "out of time for another attempt")
            report.verdict = verdict
            report.box = region
            return raw
        # raw text, not pre-labelled: openai_image.masked_prompt() adds
        # "Correction from the previous attempt:" itself, matching how
        # OutfitPiece.note is already treated for a per-item retry
        note = "; ".join(verdict.issues[:3])
    return None  # unreachable — last_chance is always true by the final attempt


async def render_masked_look(
    person: bytes,
    items: list[LookItem],
    edit: MaskedRenderFn,
    *,
    retries: int = 1,
    min_product: float = 7.0,
    min_other: float = 6.0,
    budget_seconds: int = 60,
    on_progress: ProgressFn | None = None,
) -> tuple[bytes, list[ItemReport]]:
    """Every product drawn through its own real edit mask, in as few
    sequential rounds as their windows allow — items whose masks don't
    overlap draw in parallel, since each is independently guaranteed to
    leave every other pixel alone. Returns the final image and one report
    per item — box is the exact mask window used, not a guess recovered
    from the render afterwards, because here it never was one."""
    started = time.monotonic()
    base = _cap(decode(person))
    face = detect_face(base)
    order = _order_of(items)
    reports = [ItemReport(name=item.name) for item in items]

    products = await asyncio.gather(*(_download(items[i].image_url) for i in order))
    descriptions = await asyncio.gather(
        *(describe_product(p, items[i].image_url, items[i].name) for p, i in zip(products, order))
    )
    regions = await asyncio.gather(*(_mask_region(items[i], face, base) for i in order))

    ready = []
    for step, index in enumerate(order):
        if regions[step] is None:
            reports[index].history.append("couldn't find where this goes on the photo")
        else:
            ready.append(step)

    current = base
    for wave in _waves(ready, regions):
        names = ", ".join(items[order[s]].name[:30] for s in wave)
        await _say(on_progress, f"Drawing {names}")
        results = await asyncio.gather(
            *(
                _render_item(
                    items[order[s]],
                    products[s],
                    descriptions[s],
                    regions[s],
                    current,
                    reports[order[s]],
                    edit,
                    min_p=_min_product_for(items[order[s]], min_product),
                    min_other=min_other,
                    retries=retries,
                    budget_seconds=budget_seconds,
                    started=started,
                )
                for s in wave
            )
        )
        accepted = [(step, raw) for step, raw in zip(wave, results) if raw is not None]
        if len(accepted) == 1:
            # The common case — most waves end up with exactly one item in
            # them regardless of how many run in parallel elsewhere. Take
            # the whole frame, the way single-item rendering always did:
            # every pixel, "protected" ones included, comes from the SAME
            # generation call at its one native resolution, so there is no
            # boundary for a seam to form at. Only cropping to a mask
            # rectangle (below) forces a join between two different
            # renders — worth it when two items genuinely share a round,
            # costly to pay when only one is actually there.
            current = accepted[0][1]
            continue
        if accepted:
            # Two or more items shared this round: their own masks don't
            # overlap, but each must still supply only its own rectangle —
            # taking either one's whole frame would silently erase the
            # other's edit. Upscale the shared canvas to the models' own
            # resolution first (Lanczos loses no detail going up) so the
            # paste boundary is at least a resolution match, even though a
            # boundary — and the sharpness step across it, since the
            # canvas's own pixels are an upscale, not a fresh render —
            # still exists here in a way the single-item case avoids.
            th, tw = accepted[0][1].shape[:2]
            merged = current if current.shape[:2] == (th, tw) else cv2.resize(
                current, (tw, th), interpolation=cv2.INTER_LANCZOS4
            )
            if merged is current:
                merged = merged.copy()
            for step, raw in accepted:
                if raw.shape[:2] != (th, tw):
                    raw = cv2.resize(raw, (tw, th), interpolation=cv2.INTER_LANCZOS4)
                x0, y0, x1, y1 = regions[step].pixels(tw, th)
                merged[y0:y1, x0:x1] = raw[y0:y1, x0:x1]
            current = merged

    return encode_jpeg(current, 97), reports


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("could not encode image")
    return buf.tobytes()
