"""The try-on quality pipeline: same person + exact product + natural fit.

For each item of the look, in drawing order:

1. FASHN renders the product onto the CURRENT image — which, from the
   second item on, is our merged result, not the previous raw render, so
   the model's whole-frame redraws never pile up.
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
    decode,
    draw_candidates,
    encode_jpeg,
    find_changes,
)
from app.services.tryon_quality.judge import Verdict, judge
from app.services.tryon_quality.locate import choose
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
    retries: int = 1,
    min_product: float = 7.0,
    min_other: float = 6.0,
    zoom_small: bool = False,
) -> tuple[bytes, list[ItemReport]]:
    """zoom_small: retry a failed small item (watch, jewellery) as a close-up
    — for models that can edit any photo, not only a full-body one."""
    base = _cap(decode(person))
    face = detect_face(base)
    reports: list[ItemReport] = []

    for item in items:
        report = ItemReport(item.name)
        reports.append(report)
        product = await _download(item.image_url)
        description = await describe_product(product, item.image_url, item.name)

        best: tuple[float, np.ndarray, Verdict, float] | None = None
        fix = ""
        last_region: Region | None = None
        for attempt in range(retries + 1):
            report.attempts = attempt + 1
            seed = 42 + attempt * 7919
            if zoom_small and attempt > 0 and item.slot in _SMALL and last_region is not None:
                merged, region = await _render_close_up(
                    base, last_region, item, fix, seed, render, product, description, _protect(face, item)
                )
            else:
                raw = decode(await render(encode_jpeg(base, 95), item, fix, seed))
                changes = find_changes(base, raw, _protect(face, item))
                merged, region = await _take_product(changes, product, description, item)
            if merged is not None:
                last_region = region

            if merged is None or merged.changed_share < 0.0005:
                merged = Merge(base, 0.0, 0.0, np.zeros(base.shape[:2], np.float32))
                verdict = Verdict(0, 0, 0, ["the product was not drawn on the photo"])
            else:
                try:
                    verdict = await judge(product, base, merged.image, region, description)
                except VisionError as exc:
                    # the inspector is down — don't block the customer on our outage
                    logger.warning("tryon_judge_unavailable", item=item.name[:80], error=str(exc)[:200])
                    verdict = Verdict(min_product, min_other, min_other, ["not inspected (vision unavailable)"])
            report.history.append(
                f"attempt {attempt + 1}: product={verdict.product_match:.0f} worn={verdict.worn_correctly:.0f} "
                f"realism={verdict.realism:.0f} taken={merged.changed_share:.3f}"
            )
            if best is None or verdict.score > best[0]:
                best = (verdict.score, merged.image, verdict, merged.changed_share)
            if verdict.passes(min_product, min_other):
                break
            fix = verdict.fix

        assert best is not None
        _, image, verdict, taken = best
        report.verdict, report.taken_share = verdict, taken
        logger.info("tryon_item_quality", item=item.name[:80], history=report.history)
        if not verdict.passes(min_product, min_other):
            raise QualityFailure(item.name, verdict.issues)
        base = image

    return encode_jpeg(base, 97), reports


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
    side = max(4 * max(bw, bh), 0.25 * min(h, w))
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
