"""Where is the worn product in a render? Asked of the vision model in two
passes — a rough box on the whole image, then a precise box on a zoomed-in
crop — because a watch or ring is a few dozen pixels in a full-body photo
and one pass is too coarse to cut it out cleanly."""

from __future__ import annotations

import numpy as np

from app.services.tryon_quality.compose import Region
from app.services.tryon_quality.vision import ask_json, image_part

_INSTRUCTIONS = (
    "You locate a worn fashion product in a photo of a person. Reply with JSON only: "
    '{"found": true|false, "box": [x0, y0, x1, y1]} where the box is the tightest box around the '
    "product as worn in THIS photo (not the product reference), in 0-1000 coordinates of the photo "
    "(x left->right, y top->bottom). Include straps, bracelets, laces and hems that belong to the product; "
    "exclude the person's skin and other clothing around it."
)


def _to_region(box: list, crop: tuple[float, float, float, float] = (0, 0, 1, 1)) -> Region | None:
    try:
        x0, y0, x1, y1 = (float(v) / 1000 for v in box)
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    cx0, cy0, cx1, cy1 = crop
    cw, ch = cx1 - cx0, cy1 - cy0
    return Region(cx0 + x0 * cw, cy0 + y0 * ch, cx0 + x1 * cw, cy0 + y1 * ch)


async def locate(render: np.ndarray, product: np.ndarray, description: str) -> Region | None:
    what = f"The product: {description}. The first image is the product reference, the second is the photo."
    rough = await ask_json(
        _INSTRUCTIONS, [{"type": "text", "text": what}, image_part(product, 512), image_part(render, 1024)]
    )
    if not rough.get("found"):
        return None
    region = _to_region(rough.get("box"))
    if region is None:
        return None

    # zoom in: a crop around the rough box, at least a quarter of the frame
    w, h = region.x1 - region.x0, region.y1 - region.y0
    side = max(w, h, 0.25)
    cx, cy = (region.x0 + region.x1) / 2, (region.y0 + region.y1) / 2
    crop = (max(0.0, cx - side * 0.8), max(0.0, cy - side * 0.8), min(1.0, cx + side * 0.8), min(1.0, cy + side * 0.8))
    H, W = render.shape[:2]
    zoomed = render[int(crop[1] * H) : int(crop[3] * H), int(crop[0] * W) : int(crop[2] * W)]
    fine = await ask_json(
        _INSTRUCTIONS, [{"type": "text", "text": what}, image_part(product, 512), image_part(zoomed, 1024)]
    )
    refined = _to_region(fine.get("box"), crop) if fine.get("found") else None
    return refined or region


_BODY_PART = (
    "You are shown a photo of a person. Reply with JSON only: "
    '{"found": true|false, "box": [x0, y0, x1, y1]} — the box around the body part named by the user, in 0-1000 '
    "coordinates of the photo (x left->right, y top->bottom). Be generous: include the whole part and a little "
    "around it. found is false if that part is not visible in the photo."
)


_THE_ITEM = (
    "You are shown a product photo and a photo of a person who is wearing or carrying that product. "
    "Reply with JSON only: {\"found\": true|false, \"box\": [x0, y0, x1, y1]} — the box around that product "
    "as it appears on the person, in 0-1000 coordinates of the second photo (x left->right, y top->bottom). "
    "Tight: the product itself, not the body part it is on. found is false if the product is not on the person."
)


async def find_item(photo: np.ndarray, product: np.ndarray, description: str) -> Region | None:
    """Where one product ended up on the finished photo.

    For engines whose render is used whole there is no change detection
    to take boxes from, and a marker still has to point somewhere true.
    Asking directly is both simpler and better: the old boxes came from
    whatever pixels differed, which on a whole-look render is every item
    at once."""
    answer = await ask_json(
        _THE_ITEM,
        [
            {"type": "text", "text": f"The product: {description}. First image: the product. Second: the person."},
            image_part(product, 512),
            image_part(photo, 1024),
        ],
    )
    return _to_region(answer.get("box")) if answer.get("found") else None


async def find_body_part(photo: np.ndarray, part: str) -> Region | None:
    """Where a body part is, so a tiny product (a ring, an earring) can be
    rendered on a close-up of it instead of on the whole body, where it
    would be a dozen pixels wide."""
    answer = await ask_json(
        _BODY_PART, [{"type": "text", "text": f"The body part: {part}."}, image_part(photo, 1024)]
    )
    return _to_region(answer.get("box")) if answer.get("found") else None


_CHOOSE = (
    "You are shown a product photo and a try-on photo of a person. Numbered red boxes mark every area where the "
    "try-on photo was changed. Pick the boxes that belong to the product being tried on — include a box when it "
    "contains any part of the product (straps, bracelet, laces, sleeves, hem) or the body part it is worn on that "
    "had to change with it (the hand and forearm under a watch, the legs inside new trousers). Exclude boxes that "
    'are only background, floor, lighting or unrelated clothing. Reply with JSON only: {"boxes": [numbers], '
    '"found": true|false} — found is false if the product is not visible in the photo at all.'
)


async def choose(marked: np.ndarray, product: np.ndarray, description: str, numbers: list[int]) -> list[int] | None:
    """Which of the numbered candidate areas are the product (None: not in
    the photo). Candidates come from pixel differences, so their boxes are
    exact; the vision model only has to recognise the product."""
    answer = await ask_json(
        _CHOOSE,
        [
            {"type": "text", "text": f"The product: {description}. First image: product photo. Second: try-on photo."},
            image_part(product, 512),
            image_part(marked, 1400),
        ],
    )
    if answer.get("found") is False:
        return None
    picked = answer.get("boxes") or []
    valid = [int(n) for n in picked if isinstance(n, (int, float, str)) and str(n).isdigit() and int(n) in numbers]
    return valid or None
