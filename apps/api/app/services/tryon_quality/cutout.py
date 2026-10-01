"""Background removal for a product reference photo — local, CPU-only,
cached forever per product image (same discipline as product_prep.py's
description cache: paid once per product image, never per job, and here
there isn't even a paid call, just a CPU pass).

Why this exists: a product photo is almost always shot on a white or
light-grey studio backdrop. A colour-matching check that measures the
image's dominant colour without separating product from backdrop gets
the backdrop's colour on any product that doesn't fill most of the
frame — and one that tries to exclude "bright, near-neutral" pixels
instead silently excludes white, cream, silver and light-grey PRODUCTS
too, the exact failure found in this module's first version. A real
foreground/background segmentation is the only thing that works for a
product of any colour, including white-on-white.

Model: u2netp via rembg (see docs/tryon/LICENSES.md) — MIT library,
Apache 2.0 weights, both commercial-use safe. rembg bundles other models
under other licenses (notably a BRIA-licensed one requiring a paid
commercial agreement); this file must only ever request _MODEL_NAME by
name, never a bare default.
"""

from __future__ import annotations

import hashlib

import cv2
import numpy as np

from app.core.logging import logger
from app.services.storage_service import get_storage

_MODEL_NAME = "u2netp"
_session = None


def _get_session():  # noqa: ANN202
    global _session
    if _session is None:
        from rembg import new_session

        _session = new_session(_MODEL_NAME)
    return _session


def _cache_key(image_url: str) -> str:
    return "tryon/cutout/" + hashlib.sha256(image_url.encode()).hexdigest()[:32] + ".png"


def product_cutout_mask(image: np.ndarray, image_url: str) -> np.ndarray:
    """A 0..255 alpha mask, same height/width as `image`: ~255 where the
    product is, ~0 where the studio backdrop is. Cached forever per
    product image URL — this never runs twice for the same product."""
    storage = get_storage()
    key = _cache_key(image_url)
    try:
        cached = storage.read(key)
        mask = cv2.imdecode(np.frombuffer(cached, np.uint8), cv2.IMREAD_GRAYSCALE)
        if mask is not None and mask.shape[:2] == image.shape[:2]:
            return mask
    except Exception:  # noqa: BLE001 — not cached yet, or the cache no longer matches
        pass

    try:
        from rembg import remove

        ok, buf = cv2.imencode(".png", image)
        if not ok:
            raise ValueError("could not encode product image")
        cut = remove(buf.tobytes(), session=_get_session())
        rgba = cv2.imdecode(np.frombuffer(cut, np.uint8), cv2.IMREAD_UNCHANGED)
        if rgba is None or rgba.shape[2] != 4:
            raise ValueError("cutout did not return an alpha channel")
        mask = rgba[..., 3]
        if mask.shape[:2] != image.shape[:2]:
            mask = cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    except Exception as exc:  # noqa: BLE001 — a broken cutout must not break verification
        logger.warning("tryon_cutout_failed", error=str(exc)[:200])
        return np.full(image.shape[:2], 255, dtype=np.uint8)  # fall back to "the whole photo is product"

    try:
        ok, encoded = cv2.imencode(".png", mask)
        if ok:
            storage.put(key, encoded.tobytes(), "image/png")
    except Exception as exc:  # noqa: BLE001 — caching is an optimisation
        logger.warning("tryon_cutout_cache_failed", error=str(exc)[:200])

    return mask
