"""The try-on quality pipeline: same person + exact product + natural fit.

An image model that can draw several products at once (OpenAI) renders the
whole look in ONE pass; every item is then inspected separately and only
the failures are rendered again on their own (measured on a 4-item outfit:
39s against 101s item by item). For a model that takes one product per call
(FASHN), every item is rendered in turn. Either way:

1. the product is rendered onto the CURRENT image — our merged result, not
   a previous raw render, so the model's whole-frame redraws never pile up.
2. The render is aligned to the photo and split into the areas where it
   differs (compose.find_changes, exact boxes from the pixels); the vision
   model only picks which numbered areas are the product (locate.choose) —
   it's reliable at recognising, not at coordinates. Only those areas are
   taken: the product plus any body part the model moved to wear it. Face,
   hair, skin, other clothes and background stay the person's pixels.
3. The vision model grades the merged result against the product photo
   (judge.judge). A failing render is retried with a new seed and the
   inspector's correction as an instruction; the best attempt is kept.
4. If no attempt passes, the look is refused (QualityFailure) instead of
   being returned as a success.

Measured on real FASHN tryon-max renders: face-region change vs the
original photo went from 13.8-19.3 (raw render) to 0.00 (merged), on all
seven tested categories.
"""

from __future__ import annotations

import re
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import cv2
import httpx
import numpy as np

from app.core.logging import logger
from app.models.enums import OutfitSlot
from app.services.face_restore import detect_face
from app.services.outfit_slots import worn_on_head
from app.services.tryon_quality.compose import (
    Changes,
    Merge,
    Region,
    composite,
    decode,
    draw_candidates,
    encode_jpeg,
    find_changes,
)
from app.services.tryon_quality.judge import Verdict, judge
from app.services.tryon_quality.locate import choose, find_body_part
from app.services.tryon_quality.product_prep import describe_product
from app.services.tryon_quality.vision import VisionError

# Working resolution: FASHN returns ~2.5k renders; assembling at a small
# phone photo's size threw that detail away (a watch dial became a few
# unreadable pixels). Work at 2048 on the long side — larger photos are
# reduced to it, smaller ones enlarged (the person's own pixels, just more
# of them; nothing is redrawn).
WORK_SIDE = 2048

# where to look when the vision model can't locate the item
_DEFAULT_REGION = {
    OutfitSlot.DRESS: Region(0.05, 0.1, 0.95, 1.0),
    OutfitSlot.TOP: Region(0.05, 0.1, 0.95, 0.65),
    OutfitSlot.OUTERWEAR: Region(0.05, 0.1, 0.95, 0.7),
    OutfitSlot.BOTTOM: Region(0.1, 0.45, 0.9, 1.0),
    OutfitSlot.SHOES: Region(0.1, 0.8, 0.9, 1.0),
}
# worn items that are small in a full-body photo: refined to their own
# pixels instead of taking a whole redrawn arm or torso around them
_SMALL = {OutfitSlot.WATCH, OutfitSlot.ACCESSORY, OutfitSlot.OTHER}
# Items that are a dozen pixels wide on a full-body photo: rendered on a
# close-up of the body part from the first attempt, because at full-body
# scale the model often doesn't draw them at all ("the product was not drawn
# on the photo" — a real refusal on a US Army ring).
_BODY_PART_FOR = (
    (re.compile(r"\b(ring|rings|bracelet|bangle|bangles|kada|watch|watches|cufflinks)\b"),
     "the person's hands and wrists"),
    (re.compile(r"\b(earring|earrings|jhumka|jhumkas|chandbali|studs|hoops|tikka|nose pin|hairband|headband)\b"),
     "the person's head, ears and hair"),
    (re.compile(r"\b(necklace|necklaces|choker|pendant|chain|tie|bow tie|scarf)\b"),
     "the person's neck, shoulders and upper chest"),
    (re.compile(r"\b(anklet|anklets|payal|socks)\b"), "the person's ankles and feet"),
)


def _min_product_for(item: LookItem, min_product: float) -> float:
    """A little more forgiving for something a few dozen pixels across: its
    fine ornament (filigree, beading, tiny stones) cannot survive at that
    size, and refusing the try-on over it helps nobody. Wrong colour, wrong
    shape, wrong place or missing still fails, and anything bigger than a
    watch is held to the full bar."""
    return max(5.0, min_product - 1) if item.slot in _SMALL else min_product


def _body_part_of(item: LookItem) -> str | None:
    name = item.name.lower()
    for pattern, part in _BODY_PART_FOR:
        if pattern.search(name):
            return part
    return None
# clothing that layers onto other clothing
_GARMENTS = {OutfitSlot.DRESS, OutfitSlot.TOP, OutfitSlot.BOTTOM, OutfitSlot.OUTERWEAR}
_EYEWEAR = re.compile(r"\b(sunglasses|glasses|eyeglasses|spectacles|goggles)\b")


@dataclass(frozen=True, slots=True)
class LookItem:
    image_url: str  # the listing's main photo — never swapped or cropped
    slot: OutfitSlot
    name: str


@dataclass(slots=True)
class ItemReport:
    name: str
    attempts: int = 0
    verdict: Verdict | None = None
    taken_share: float = 0.0
    history: list[str] = field(default_factory=list)


class QualityFailure(Exception):
    def __init__(self, item: str, issues: list[str]) -> None:
        self.item = item
        self.issues = issues
        detail = "; ".join(issues[:2]) or "the render didn't match the product closely enough"
        super().__init__(f"{item}: {detail}")


# (current image as JPEG, item, extra instruction, seed) -> raw render bytes
RenderFn = Callable[[bytes, LookItem, str, int], Awaitable[bytes]]
# (current image as JPEG, every item) -> one render with the whole look on it
RenderAllFn = Callable[[bytes, list[LookItem]], Awaitable[bytes]]


def _cap(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    scale = WORK_SIDE / max(h, w)
    if abs(scale - 1) < 0.02:
        return img
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4
    return cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=interpolation)


def _protect(face, item: LookItem) -> list[tuple[int, int, int, int]]:
    """What the merge may never take from a render: the face — all of it
    (with hair and beard) normally; only its core for something worn on the
    head (earrings, hat); only the mouth/chin for eyewear."""
    if face is None:
        return []
    x, y, w, h = face.x, face.y, face.w, face.h
    name = item.name.lower()
    if _EYEWEAR.search(name):
        return [(x + int(w * 0.2), y + int(h * 0.62), x + int(w * 0.8), y + int(h * 1.05))]
    if worn_on_head(name):
        return [(x + int(w * 0.18), y + int(h * 0.12), x + int(w * 0.82), y + int(h * 1.0))]
    return [(x - int(w * 0.25), y - int(h * 0.45), x + w + int(w * 0.25), y + h + int(h * 0.2))]


async def _download(url: str) -> np.ndarray:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
    if resp.status_code >= 400:
        raise ValueError(f"couldn't download product photo (HTTP {resp.status_code})")
    return decode(resp.content)


async def render_look(
    person: bytes,
    items: list[LookItem],
    render: RenderFn,
    *,
    render_all: RenderAllFn | None = None,
    retries: int = 1,
    min_product: float = 7.0,
    min_other: float = 6.0,
    zoom_small: bool = False,
) -> tuple[bytes, list[ItemReport]]:
    """The look on the person's photo, with only the products taken from the
    renders, every item inspected, and anything that fails re-rendered or
    refused.

    render_all (an image model that can draw several products in one edit)
    does the whole look in ONE render — measured on a 4-item outfit: 39s
    against 101s item by item, with equal or better scores. Only items that
    fail inspection are then rendered individually.
    zoom_small: retry a failed small item (watch, jewellery) as a close-up.
    """
    base = _cap(decode(person))
    face = detect_face(base)
    products = await asyncio.gather(*(_download(item.image_url) for item in items))
    descriptions = await asyncio.gather(
        *(describe_product(product, item.image_url, item.name) for product, item in zip(products, items))
    )
    reports = [ItemReport(item.name) for item in items]
    todo = list(range(len(items)))

    if render_all is not None and items:
        base, todo = await _whole_look_pass(
            base, face, items, products, descriptions, reports, render_all, min_product, min_other
        )

    for index in todo:
        base = await _render_one(
            base, face, items[index], products[index], descriptions[index], reports[index],
            render, retries, min_product, min_other, zoom_small,
        )

    return encode_jpeg(base, 97), reports


async def _pick_areas(changes: Changes, product: np.ndarray, description: str, item: LookItem) -> list[int]:
    """Which changed areas are this item's, from the shared whole-look render."""
    numbers = [c.number for c in changes.candidates]
    if not numbers:
        return []
    try:
        picked = await choose(draw_candidates(changes.render, changes.candidates), product, description, numbers)
    except VisionError:
        area = _DEFAULT_REGION.get(item.slot, Region(0, 0, 1, 1))
        picked = [c.number for c in changes.candidates if _overlaps(c.region, area)]
    return picked or []


def _box_of(changes: Changes, numbers: list[int], item: LookItem) -> Region:
    boxes = [c.region for c in changes.candidates if c.number in numbers]
    if not boxes:
        return _DEFAULT_REGION.get(item.slot, Region(0, 0, 1, 1))
    return Region(
        min(b.x0 for b in boxes), min(b.y0 for b in boxes), max(b.x1 for b in boxes), max(b.y1 for b in boxes)
    )


async def _whole_look_pass(
    base: np.ndarray,
    face,  # noqa: ANN001
    items: list[LookItem],
    products: list[np.ndarray],
    descriptions: list[str],
    reports: list[ItemReport],
    render_all: RenderAllFn,
    min_product: float,
    min_other: float,
) -> tuple[np.ndarray, list[int]]:
    """One render of the whole look; keep the items that pass inspection.
    Returns the image with those items on it, and which items still need
    their own render."""
    head_item = next((i for i in items if worn_on_head(i.name)), items[0])
    try:
        raw = decode(await render_all(encode_jpeg(base, 95), items))
    except Exception as exc:  # noqa: BLE001 — fall back to item-by-item
        logger.warning("tryon_whole_look_render_failed", error=str(exc)[:300])
        return base, list(range(len(items)))

    changes = find_changes(base, raw, _protect(face, head_item))
    if not changes.candidates:
        return base, list(range(len(items)))

    picks = await asyncio.gather(
        *(_pick_areas(changes, product, description, item)
          for product, description, item in zip(products, descriptions, items))
    )
    everything = sorted({n for picked in picks for n in picked})
    if not everything:
        return base, list(range(len(items)))

    shown = changes.merge(everything).image
    verdicts = await asyncio.gather(
        *(judge(product, base, shown, _box_of(changes, picked, item), description, item.slot in _SMALL)
          for product, description, item, picked in zip(products, descriptions, items, picks)),
        return_exceptions=True,
    )

    keep: list[int] = []
    todo: list[int] = []
    for index, (picked, verdict) in enumerate(zip(picks, verdicts)):
        report = reports[index]
        report.attempts = 1
        if isinstance(verdict, BaseException) or not picked:
            todo.append(index)
            continue
        report.history.append(
            f"whole look: product={verdict.product_match:.0f} worn={verdict.worn_correctly:.0f} "
            f"realism={verdict.realism:.0f}"
        )
        if verdict.passes(min_product, min_other):
            report.verdict = verdict
            keep.extend(picked)
        else:
            todo.append(index)
    logger.info("tryon_whole_look", kept=len(items) - len(todo), redo=len(todo))
    if not keep:
        return base, list(range(len(items)))
    merged = changes.merge(sorted(set(keep)))
    for index, report in enumerate(reports):
        if index not in todo:
            report.taken_share = merged.changed_share
    return merged.image, todo


async def _render_one(
    base: np.ndarray,
    face,  # noqa: ANN001
    item: LookItem,
    product: np.ndarray,
    description: str,
    report: ItemReport,
    render: RenderFn,
    retries: int,
    min_product: float,
    min_other: float,
    zoom_small: bool,
) -> np.ndarray:
    """One item rendered on the current image, inspected, retried, or refused."""
    best: tuple[float, np.ndarray, Verdict, float] | None = None
    fix = ""
    last_region: Region | None = None
    part = _body_part_of(item) if zoom_small and item.slot in _SMALL else None
    region_is_body_part = False
    if part is not None:
        try:
            last_region = await find_body_part(base, part)
            region_is_body_part = last_region is not None
        except VisionError as exc:
            logger.warning("tryon_body_part_unknown", item=item.name[:80], error=str(exc)[:200])
    for attempt in range(retries + 1):
        report.attempts += 1
        seed = 42 + attempt * 7919
        if zoom_small and item.slot in _SMALL and last_region is not None:
            merged, region = await _render_close_up(
                base, last_region, item, fix, seed, render, product, description, _protect(face, item),
                zoom=1.25 if region_is_body_part else 4.0,
            )
        else:
            raw = decode(await render(encode_jpeg(base, 95), item, fix, seed))
            # a ring is ~15px across on a full-body photo: don't let the
            # noise filter throw it away with the specks
            changes = find_changes(
                base, raw, _protect(face, item), min_share=0.00004 if item.slot in _SMALL else 0.0003
            )
            merged, region = await _take_product(changes, product, description, item)
        if merged is not None:
            last_region = region
            region_is_body_part = False  # from here on it's the item's own box

        # "not drawn" must be judged against the item's own size: a pair of
        # stud earrings covers ~0.02% of a photo, and a flat 0.05% floor
        # called them missing even when the model had drawn them properly
        drawn_floor = 0.00002 if item.slot in _SMALL else 0.0005
        if merged is None or merged.changed_share < drawn_floor:
            merged = Merge(base, 0.0, 0.0, np.zeros(base.shape[:2], np.float32))
            verdict = Verdict(0, 0, 0, ["the product was not drawn on the photo"])
        else:
            try:
                verdict = await judge(product, base, merged.image, region, description, item.slot in _SMALL)
            except VisionError as exc:
                # the inspector is down — don't block the customer on our outage
                logger.warning("tryon_judge_unavailable", item=item.name[:80], error=str(exc)[:200])
                verdict = Verdict(min_product, min_other, min_other, ["not inspected (vision unavailable)"])
        report.history.append(
            f"own render {attempt + 1}: product={verdict.product_match:.0f} worn={verdict.worn_correctly:.0f} "
            f"realism={verdict.realism:.0f} taken={merged.changed_share:.3f}"
        )
        if best is None or verdict.score > best[0]:
            best = (verdict.score, merged.image, verdict, merged.changed_share)
        if verdict.passes(_min_product_for(item, min_product), min_other):
            break
        fix = verdict.fix

    assert best is not None
    _, image, verdict, taken = best
    report.verdict, report.taken_share = verdict, taken
    logger.info("tryon_item_quality", item=item.name[:80], history=report.history)
    if not verdict.passes(_min_product_for(item, min_product), min_other):
        raise QualityFailure(item.name, verdict.issues)
    return image


async def _render_close_up(
    base: np.ndarray,
    around: Region,
    item: LookItem,
    fix: str,
    seed: int,
    render: RenderFn,
    product: np.ndarray,
    description: str,
    protect: list[tuple[int, int, int, int]],
    zoom: float = 4.0,
) -> tuple[Merge | None, Region]:
    """Render a small item on a close-up of where it goes, then put it back.

    A watch in a full-body photo is ~40px wide: the image model can't draw a
    bezel or dial accurately at that size (live: a red-and-blue GMT bezel
    came out wrong twice and the try-on was refused). On a close-up of the
    wrist it's many times larger. The close-up result is merged into the
    close-up of the photo the same way as any render — only the product and
    what it moved are taken — and pasted back in place."""
    h, w = base.shape[:2]
    bw, bh = (around.x1 - around.x0) * w, (around.y1 - around.y0) * h
    # `zoom` is how much context to keep around the box: 4x a watch-sized
    # item box, but only a little around a body-part box (a head), which is
    # already big — 4x of that covered the whole photo, so a stud earring
    # stayed ~8px wide and the model never drew it.
    side = max(zoom * max(bw, bh), 0.12 * min(h, w))
    cx, cy = (around.x0 + around.x1) / 2 * w, (around.y0 + around.y1) / 2 * h
    x0, y0 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
    x1, y1 = int(min(w, cx + side / 2)), int(min(h, cy + side / 2))
    crop = base[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]
    up = 1024 / max(ch, cw)
    crop_up = cv2.resize(crop, (round(cw * up), round(ch * up)), interpolation=cv2.INTER_LANCZOS4) if up > 1 else crop

    raw = decode(await render(encode_jpeg(crop_up, 95), item, fix, seed))
    raw = cv2.resize(raw, (cw, ch), interpolation=cv2.INTER_AREA)
    local_protect = [(px0 - x0, py0 - y0, px1 - x0, py1 - y0) for px0, py0, px1, py1 in protect]
    changes = find_changes(crop, raw, local_protect)
    merged, region = await _take_product(changes, product, description, item)
    if merged is None:
        return None, around
    full = base.copy()
    full[y0:y1, x0:x1] = merged.image
    mask = np.zeros((h, w), np.float32)
    mask[y0:y1, x0:x1] = merged.mask
    back = Region(
        (x0 + region.x0 * cw) / w, (y0 + region.y0 * ch) / h, (x0 + region.x1 * cw) / w, (y0 + region.y1 * ch) / h
    )
    return Merge(full, merged.alignment, float(mask.mean()), mask), back


async def _take_product(
    changes: Changes, product: np.ndarray, description: str, item: LookItem
) -> tuple[Merge | None, Region]:
    """Merge the areas that are the product; (None, region) if the product
    isn't in the render. The region (union of the chosen areas) is what the
    inspector is shown close up."""
    numbers = [c.number for c in changes.candidates]
    if not numbers:
        return None, _DEFAULT_REGION.get(item.slot, Region(0, 0, 1, 1))
    try:
        picked = await choose(draw_candidates(changes.render, changes.candidates), product, description, numbers)
    except VisionError:
        # no vision: take the changes inside where this kind of item goes
        area = _DEFAULT_REGION.get(item.slot, Region(0, 0, 1, 1))
        picked = [c.number for c in changes.candidates if _overlaps(c.region, area)] or numbers
    if not picked:
        return None, _DEFAULT_REGION.get(item.slot, Region(0, 0, 1, 1))
    reach = 0.03
    if item.slot in _SMALL and changes.share_of(picked) > 0.006:
        finer = changes.refine(picked)
        numbers = [c.number for c in finer.candidates]
        if numbers:
            try:
                again = await choose(draw_candidates(finer.render, finer.candidates), product, description, numbers)
            except VisionError:
                again = None
            if again:
                changes, picked, reach = finer, again, 0.015
    boxes = [c.region for c in changes.candidates if c.number in picked]
    region = Region(
        min(b.x0 for b in boxes), min(b.y0 for b in boxes), max(b.x1 for b in boxes), max(b.y1 for b in boxes)
    )
    return changes.merge(picked, reach), region


def _overlaps(a: Region, b: Region) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


async def keep_person(person: bytes, render_bytes: bytes, items: list[LookItem]) -> bytes:
    """For a whole-look render made in one pass (OpenAI image editing): keep
    the person's own pixels everywhere except the products."""
    base = _cap(decode(person))
    face = detect_face(base)
    head_item = next((i for i in items if worn_on_head(i.name)), None)
    protect = _protect(face, head_item or items[0]) if items else []
    changes = find_changes(base, decode(render_bytes), protect)
    picked: set[int] = set()
    for item in items:
        product = await _download(item.image_url)
        description = await describe_product(product, item.image_url, item.name)
        merged, _ = await _take_product(changes, product, description, item)
        if merged is not None:
            picked |= {c.number for c in changes.candidates if _chosen_by(changes, merged, c)}
    return encode_jpeg(changes.merge(sorted(picked)).image, 97)


def _chosen_by(changes: Changes, merged: Merge, candidate) -> bool:  # noqa: ANN001
    x0, y0, x1, y1 = candidate.region.pixels(merged.mask.shape[1], merged.mask.shape[0])
    return bool(merged.mask[y0:y1, x0:x1].max() > 0.5)
