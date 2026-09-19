"""What exactly is this product? — a detail description for the steps that
must recognise it (locating it in the render, grading the result).

The product IMAGE is never altered: the try-on model always gets the
listing's main photo, the one the shopper chose. Tested on real eBay
listings, letting a vision model pick a "cleaner" photo or crop to the
product was worse than useless — it picked a white colour variant of a
black shirt, cut a watch in half and cropped chinos to one leg, i.e. it
swapped or damaged the product. FASHN coped with the uncropped main photos
(packaging, on-model shots) fine.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from app.core.logging import logger
from app.services.storage_service import get_storage
from app.services.tryon_quality.vision import VisionError, ask_json, image_part

_INSTRUCTIONS = (
    "Describe the product in a retailer photo so an inspector can tell it apart from similar products. "
    'Reply with JSON only: {"description": "one sentence: item type, then every detail that must be reproduced '
    "exactly — colours, pattern, material, logo/print, buttons, zips, hardware, strap/bracelet, sole, dial. "
    'Describe the product the listing sells, not other items in the photo (packaging, the model\'s other clothes). '
    'Colours as they APPEAR in the photo — listing titles are often wrong (an "espresso" bag that is black)."}'
)


def _cache_key(image_url: str) -> str:
    return "tryon/described/" + hashlib.sha256(image_url.encode()).hexdigest()[:32] + ".json"


async def describe_product(image: np.ndarray, image_url: str, name: str) -> str:
    """A detail description of the product in its main photo; the product's
    name if the vision model is unavailable. Cached per photo."""
    storage = get_storage()
    key = _cache_key(image_url)
    try:
        return json.loads(storage.read(key))["description"]
    except Exception:  # noqa: BLE001 — not cached yet
        pass
    try:
        answer = await ask_json(
            _INSTRUCTIONS, [{"type": "text", "text": f"Listing title: {name}"}, image_part(image, 768)]
        )
        description = str(answer.get("description") or name)[:400]
    except VisionError as exc:
        logger.warning("tryon_describe_fallback", product=name[:80], error=str(exc)[:200])
        return name
    try:
        storage.put(key, json.dumps({"description": description}).encode(), "application/json")
    except Exception as exc:  # noqa: BLE001 — caching is an optimisation
        logger.warning("tryon_describe_cache_failed", error=str(exc)[:200])
    return description
