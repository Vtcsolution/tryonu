"""One image showing a whole look, built from the products a shopper selected.

FASHN Try-On Max takes ONE product image per call, but that image may show a
complete outfit: live, a single look image (a model wearing a bridal dress,
dupatta, tikka, earrings, necklace, rings, watch, clutch and khussa) went in
as `product_image` and all nine came out on the customer, in one 2-credit
call, clean. A shopper's products are separate retailer photos, so this
composes them into one such image: each product cut out onto white,
garments large on the left, everything else beside them, each labelled with
what it is so the model knows where it goes.

Pure image work on our own server: no network, nothing paid.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.logging import logger

BOARD_SIZE = (1536, 2048)  # 3:4 portrait, the shape of a full-body look
_MARGIN = 28
_LABEL_H = 54
_GARMENT_SHARE = 0.58  # of the width, when there are other products beside them

_LABELS = [
    # watch before bangles: a "Gold Bracelet Watch" is a watch (live, it was
    # labelled Bangles and came out as gold bangles nobody selected)
    (re.compile(r"\b(watch|watches|wristwatch)\b", re.I), "Watch"),
    (re.compile(r"\b(nose ?(rings?|pins?|studs?)|nath|nathni)\b", re.I), "Nose ring"),
    (re.compile(r"\b(maang ?tikka|tikka|matha ?patti|head ?chain)\b", re.I), "Maang tikka"),
    (re.compile(r"\b(earrings?|jhumkas?|jhumki|studs?|chandbali)\b", re.I), "Earrings"),
    (re.compile(r"\b(choker|necklace|haar|pendant)\b", re.I), "Necklace"),
    (re.compile(r"\b(bangles?|bracelets?|kada|cuff)\b", re.I), "Bangles"),
    (re.compile(r"\b(rings?)\b", re.I), "Ring"),
    (re.compile(r"\b(sunglasses|glasses|eyeglasses)\b", re.I), "Sunglasses"),
    (re.compile(r"\b(khussa|jutti|heels|sandals?|shoes|sneakers|flats|boots|loafers)\b", re.I), "Shoes"),
    (re.compile(r"\b(clutch|clutches)\b", re.I), "Clutch"),
    (re.compile(r"\b(clutch|handbag|bag|tote|purse|potli)\b", re.I), "Bag"),
    (re.compile(r"\b(dupatta|stole|shawl|scarf)\b", re.I), "Dupatta"),
]

KNOWN_LABELS = frozenset(label for _, label in _LABELS)


@dataclass(frozen=True)
class BoardItem:
    image: bytes
    image_url: str
    name: str
    garment: bool


def label_for(name: str, garment: bool) -> str:
    # A garment is always the whole outfit, whatever its title mentions.
    # Live: "Pink Embroidered Lehenga Choli with Dupatta" was labelled
    # "Dupatta", and FASHN drew only the dupatta over an invented plain suit.
    if garment:
        return "Outfit"
    for pattern, label in _LABELS:
        if pattern.search(name):
            return label
    words = re.findall(r"[A-Za-z]+", name)
    return " ".join(words[:3]) or "Product"


def _decode(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    return img


def _below_the_head(bgr: np.ndarray) -> int:
    """The first row under a model's head in a clothing photo, or 0 when no
    face is found in its upper half. Live: a lehenga worn by a fair-skinned
    model went onto the board with her face and arms, and the customer came
    back with a lighter skin tone; the mannequin-photo looks kept theirs."""
    from app.services.tryon_direct.qc import _face_candidates

    h = bgr.shape[0]
    faces = [f for f in _face_candidates(bgr) if f.y + f.h / 2 < h * 0.5]
    if not faces:
        return 0
    face = max(faces, key=lambda f: f.w * f.h)
    return min(h - 1, int(face.y + face.h * 1.35))  # past the chin, into the neckline


def _without_people(bgr: np.ndarray, item: BoardItem, mask: np.ndarray, top: int) -> tuple[np.ndarray, np.ndarray]:
    """An accessory's photo and mask without any hand, arm or face holding or
    wearing it. Where the hand covered the product (fingers over a clutch's
    corner), the gap inside the product's own outline is filled from the
    product around it, so the board shows no bite out of it. Kept as is when
    the person would take most of the product with them (earrings
    photographed on an ear are found as part of the person)."""
    from app.services.tryon_quality.cutout import person_mask

    person = (person_mask(bgr if top == 0 else _decode(item.image), item.image_url)[top:] > 127).astype(np.uint8)
    person = cv2.dilate(person, np.ones((9, 9), np.uint8))
    product = mask > 127
    kept = product & (person == 0)
    if not person.any() or product.sum() == 0 or kept.sum() < 0.5 * product.sum():
        return bgr, mask
    hull = np.zeros(mask.shape, np.uint8)
    points = cv2.findNonZero(kept.astype(np.uint8))
    cv2.fillConvexPoly(hull, cv2.convexHull(points), 1)
    gap = ((person > 0) & (hull > 0)).astype(np.uint8)
    filled = bgr
    if gap.any():
        # Bags, watches and jewellery are close to symmetric left to right:
        # the gap takes the mirrored pixels from the clean side, real texture
        # rather than a smear. What has no clean mirror is inpainted from the
        # product only (hand and backdrop first set to the product's colour).
        filled = bgr.copy()
        x0, _, w, _ = cv2.boundingRect(points)
        ys, xs = np.nonzero(gap)
        mx = np.clip(2 * x0 + w - 1 - xs, 0, bgr.shape[1] - 1)
        clean = kept[ys, mx] & (gap[ys, mx] == 0)
        filled[ys[clean], xs[clean]] = bgr[ys[clean], mx[clean]]
        rest = gap.copy()
        rest[ys[clean], xs[clean]] = 0
        if rest.any():
            filled[~kept & (gap == 0)] = np.median(bgr[kept], axis=0).astype(np.uint8)
            filled = cv2.inpaint(filled, rest, 7, cv2.INPAINT_TELEA)
    out = np.where(person > 0, 0, mask).astype(mask.dtype)
    out[gap > 0] = 255
    return filled, out


def _cut_out(item: BoardItem) -> Image.Image:
    """The product on white, cropped to itself. The original photo, uncut,
    when background removal fails: a product is never dropped from the board.
    A garment worn by a model loses the model's head, so only the clothing
    is shown, never another person's face or skin."""
    whole = _decode(item.image)
    top = 0
    if item.garment:
        try:
            top = _below_the_head(whole)
        except Exception as exc:  # noqa: BLE001 — keep the whole photo
            logger.info("look_board_face_check_skipped", product=item.name[:60], error=str(exc)[:120])
    bgr = whole[top:]
    try:
        from app.services.tryon_quality.cutout import product_cutout_mask

        mask = product_cutout_mask(whole, item.image_url)[top:]  # cached for the whole photo
        if not item.garment:
            bgr, mask = _without_people(bgr, item, mask, top)
        keep = mask > 127
        if keep.mean() < 0.01:  # nothing found: keep the whole photo
            raise ValueError("empty cutout")
        ys, xs = np.nonzero(keep)
        pad = 12
        y0, y1 = max(0, ys.min() - pad), min(bgr.shape[0], ys.max() + pad)
        x0, x1 = max(0, xs.min() - pad), min(bgr.shape[1], xs.max() + pad)
        alpha = (mask.astype(np.float32) / 255.0)[..., None]
        white = np.full_like(bgr, 255)
        on_white = (bgr * alpha + white * (1 - alpha)).astype(np.uint8)[y0:y1, x0:x1]
    except Exception as exc:  # noqa: BLE001 — keep the product, uncut
        logger.info("look_board_cutout_skipped", product=item.name[:60], error=str(exc)[:120])
        on_white = bgr
    return Image.fromarray(cv2.cvtColor(on_white, cv2.COLOR_BGR2RGB))


def _place(canvas: Image.Image, draw: ImageDraw.ImageDraw, img: Image.Image, box: tuple[int, int, int, int], label: str, font) -> None:  # noqa: ANN001
    x0, y0, x1, y1 = box
    area_w, area_h = x1 - x0, y1 - y0 - _LABEL_H
    scale = min(area_w / img.width, area_h / img.height)
    fitted = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    canvas.paste(fitted, (x0 + (area_w - fitted.width) // 2, y0 + (area_h - fitted.height) // 2))
    text_w = draw.textlength(label, font=font)
    draw.text((x0 + (area_w - text_w) / 2, y1 - _LABEL_H + 8), label, fill=(30, 30, 30), font=font)


def _grid(n: int, box: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    x0, y0, x1, y1 = box
    cols = 1 if n <= 4 else 2
    rows = -(-n // cols)
    cw, ch = (x1 - x0) / cols, (y1 - y0) / rows
    return [
        (int(x0 + c * cw), int(y0 + r * ch), int(x0 + (c + 1) * cw) - _MARGIN // 2, int(y0 + (r + 1) * ch) - _MARGIN // 2)
        for i in range(n)
        for r, c in [divmod(i, cols)]
    ]


def build_look_board(items: list[BoardItem]) -> tuple[bytes, list[str]]:
    """The board as PNG bytes, and the label given to each item (same order)."""
    if not items:
        raise ValueError("no products for the look board")
    w, h = BOARD_SIZE
    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=34)
    labels = [label_for(i.name, i.garment) for i in items]

    garments = [k for k, i in enumerate(items) if i.garment]
    others = [k for k, i in enumerate(items) if not i.garment]
    inner = (_MARGIN, _MARGIN, w - _MARGIN, h - _MARGIN)
    if garments and others:
        split = int(w * _GARMENT_SHARE)
        garment_boxes = _grid_rows(len(garments), (inner[0], inner[1], split, inner[3]))
        other_boxes = _grid(len(others), (split + _MARGIN, inner[1], inner[2], inner[3]))
    elif garments:
        garment_boxes, other_boxes = _grid_rows(len(garments), inner), []
    else:
        garment_boxes, other_boxes = [], _grid(len(others), inner)

    for k, box in zip(garments, garment_boxes):
        _place(canvas, draw, _cut_out(items[k]), box, labels[k], font)
    for k, box in zip(others, other_boxes):
        _place(canvas, draw, _cut_out(items[k]), box, labels[k], font)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue(), labels


def _grid_rows(n: int, box: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    x0, y0, x1, y1 = box
    rh = (y1 - y0) / n
    return [(x0, int(y0 + r * rh), x1, int(y0 + (r + 1) * rh) - _MARGIN // 2) for r in range(n)]
