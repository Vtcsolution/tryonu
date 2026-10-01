"""Where on the body a product goes, what draws over what, and how it
conforms to the body — derived ONLY from the product's own photo, never
its title or category label.

A listing title can say anything ("Classic 6 Rings Sneaker" is shoes, not
jewellery — docs/tryon/AUDIT.md's own title/keyword mis-placement entry)
and retailer categories are inconsistent across providers (AUDIT.md §4) —
neither is trusted here. Only what the photo actually shows decides the
zone.

Cached forever per product image URL, same discipline as
product_prep.describe_product() and cutout.product_cutout_mask(): one
vision call per product image, ever, never once per job.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

import numpy as np

from app.core.logging import logger
from app.services.storage_service import get_storage
from app.services.tryon_quality.vision import VisionError, ask_json, image_part

# A closed, body-geometry vocabulary — not a product category. Mirrors the
# zones masked.py's own mask regions already handle (dress/top/bottom/
# outerwear/shoes/bag + the face-relative small-item windows), so the
# zoned pipeline's geometry lookup (zoned.py) can reuse that proven
# windowing rather than invent new numbers.
ZONES = (
    "full_body", "torso", "lower_body", "outerwear", "feet",
    "hand_wrist", "neck_chest", "ears", "forehead", "eyewear", "head_other", "bag", "other",
)

# A product in one of these zones is worn over a large share of the body —
# it goes in the large-region pass (max 3 per call); everything else is a
# small-region accessory, rendered in its own zoomed pass (max 2-3 per
# call) — see zoned.py's own staging rule.
_LARGE_ZONES = {"full_body", "torso", "lower_body", "outerwear"}

_INSTRUCTIONS = (
    "Look ONLY at this product photo. Ignore any name or category you may already know about it — classify purely "
    "from what the image shows. Reply with JSON only: "
    '{"zone": one of ["full_body","torso","lower_body","outerwear","feet","hand_wrist","neck_chest","ears",'
    '"forehead","eyewear","head_other","bag","other"] (where on a body this sits), '
    '"layer": 0-5 (draw order if several products are worn together: 0 = innermost/first, like a base garment '
    "under everything else; higher numbers draw on top of lower ones, e.g. outerwear over a top, a bracelet over a "
    'sleeve), '
    '"deformation": "one short phrase on how this conforms to a body as worn — e.g. drapes over the torso and '
    'follows its contour, wraps cylindrically around the wrist, rigid flat shape that does not bend, follows the '
    'foot\'s shape with ground contact", '
    '"large_region": true if this is worn over a large area of the body (a garment covering the torso and/or legs), '
    'false if it occupies only a small area (jewellery, a watch, a bag, eyewear, a single shoe)}'
)


@dataclass(frozen=True, slots=True)
class ZoneSpec:
    zone: str
    layer: int
    deformation: str
    large_region: bool


_FALLBACK = ZoneSpec(zone="other", layer=3, deformation="", large_region=False)


def _cache_key(image_url: str) -> str:
    return "tryon/zone-spec/" + hashlib.sha256(image_url.encode()).hexdigest()[:32] + ".json"


def _from_json(data: dict) -> ZoneSpec:
    zone = str(data.get("zone") or "other")
    if zone not in ZONES:
        zone = "other"
    return ZoneSpec(
        zone=zone,
        layer=max(0, min(5, int(data.get("layer", 3) or 3))),
        deformation=str(data.get("deformation") or "")[:160],
        large_region=bool(data.get("large_region", zone in _LARGE_ZONES)),
    )


async def zone_spec_for(product_image: np.ndarray, product_image_url: str) -> ZoneSpec:
    """This product's zone/layer/deformation, from its photo alone.
    Cached per image URL; falls back to a conservative small-item default
    ("other", drawn last, small region) if the vision model is
    unavailable — never crashes a render over this."""
    storage = get_storage()
    key = _cache_key(product_image_url)
    try:
        return _from_json(json.loads(storage.read(key)))
    except Exception:  # noqa: BLE001 — not cached yet
        pass
    try:
        answer = await ask_json(_INSTRUCTIONS, [image_part(product_image, 768)])
        spec = _from_json(answer)
    except VisionError as exc:
        logger.warning("tryon_zone_spec_fallback", error=str(exc)[:200])
        return _FALLBACK
    try:
        storage.put(key, json.dumps(asdict(spec)).encode(), "application/json")
    except Exception as exc:  # noqa: BLE001 — caching is an optimisation
        logger.warning("tryon_zone_spec_cache_failed", error=str(exc)[:200])
    return spec
