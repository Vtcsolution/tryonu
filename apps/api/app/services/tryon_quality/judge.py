"""Grade a try-on before it's returned — so a poor render is retried or
refused instead of being reported as a success.

Identity isn't asked of the vision model: the merge keeps the person's
own pixels outside the product area, and that's checked by measurement
(see pipeline._identity_kept). The vision model grades what only it can:
is this the exact product, is it worn the way a real one would be, does
it look like a photograph."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.services.tryon_quality.compose import Region
from app.services.tryon_quality.vision import ask_json, image_part

_INSTRUCTIONS = (
    "You are a strict quality inspector for virtual try-on photos. You get: (1) the product reference photo, "
    "(2) the person BEFORE, cropped to where the product goes, (3) the person AFTER, same crop, (4) the whole "
    "AFTER photo. Judge ONLY the product being tried on. The reference PHOTO is the ground truth — the text "
    "description is only a hint and may be wrong. Judge details at the resolution the AFTER photo allows: don't "
    "mark down a logo or dial text simply for being too small to read at this size, but do mark down wrong "
    "colours, shapes, patterns or hardware. Reply with JSON only:\n"
    '{"product_match": 0-10 (is it the SAME product as the reference: colour, pattern, print/logo, material, '
    "shape, buttons/zips/hardware, dial/strap, sole — 10 identical, 7 minor detail drift, 4 similar-looking "
    'but different product, 0 wrong or missing), '
    '"worn_correctly": 0-10 (placed where it belongs and fitted to THIS body and pose: garment covers the torso/'
    "legs with correct shoulders, sleeves, collar, waist and hem; watch wraps AROUND the wrist in perspective, "
    "not flat; shoes on the correct feet with correct perspective and ground contact; bag strap follows the "
    'shoulder/body; proportions realistic), '
    '"realism": 0-10 (lighting, shadows and occlusion consistent with the photo, no pasted-on look, no seams, '
    'halos, duplicated limbs, warped hands or other artifacts), '
    '"issues": ["short concrete problems, empty if none"], '
    '"fix": "one short instruction to the try-on model that would fix the most important problem, or empty"}'
)


@dataclass(frozen=True, slots=True)
class Verdict:
    product_match: float
    worn_correctly: float
    realism: float
    issues: list[str] = field(default_factory=list)
    fix: str = ""

    @property
    def score(self) -> float:
        return self.product_match * 0.45 + self.worn_correctly * 0.35 + self.realism * 0.2

    def passes(self, min_product: float, min_other: float) -> bool:
        return (
            self.product_match >= min_product
            and self.worn_correctly >= min_other
            and self.realism >= min_other
        )


def _crop(img: np.ndarray, region: Region, pad: float = 0.6) -> np.ndarray:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = region.pixels(w, h, pad)
    crop = img[y0:y1, x0:x1]
    # a watch crop from a full-body photo is ~100px; shown that small the
    # inspector only ever answered "too small to verify" — enlarge it
    ch, cw = crop.shape[:2]
    if 0 < max(ch, cw) < 640:
        scale = 640 / max(ch, cw)
        crop = cv2.resize(crop, (round(cw * scale), round(ch * scale)), interpolation=cv2.INTER_CUBIC)
    return crop


def _num(value: object) -> float:
    try:
        return max(0.0, min(10.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


_SMALL_ITEM_NOTE = (
    "This product covers only a small part of the photo (a watch is ~40px wide in a full-body shot), so its "
    "close-up here is an enlargement of very few pixels. Judge what is actually resolvable at that size: "
    "case/dial/strap COLOURS, shape, proportions and how it is worn. Do NOT mark it down for unreadable text, "
    "numerals, logos, stitching or engraving — a customer cannot see those either, and fine ornament (filigree, "
    "beading, tiny stones) is necessarily simplified at this size. Mark it down only if the colours, the overall "
    "silhouette/shape or the placement are wrong, or the item is missing."
)


async def judge(
    product: np.ndarray,
    before: np.ndarray,
    after: np.ndarray,
    region: Region,
    description: str,
    small_item: bool = False,
) -> Verdict:
    answer = await ask_json(
        _INSTRUCTIONS + ("\n" + _SMALL_ITEM_NOTE if small_item else ""),
        [
            {"type": "text", "text": f"The product: {description}"},
            {"type": "text", "text": "(1) product reference:"},
            image_part(product, 768),
            {"type": "text", "text": "(2) BEFORE, product area:"},
            image_part(_crop(before, region), 768),
            {"type": "text", "text": "(3) AFTER, product area:"},
            image_part(_crop(after, region), 768),
            {"type": "text", "text": "(4) whole AFTER photo:"},
            image_part(after, 1024),
        ],
    )
    issues = answer.get("issues") or []
    return Verdict(
        product_match=_num(answer.get("product_match")),
        worn_correctly=_num(answer.get("worn_correctly")),
        realism=_num(answer.get("realism")),
        issues=[str(i)[:160] for i in issues][:6] if isinstance(issues, list) else [],
        fix=str(answer.get("fix") or "")[:200],
    )
