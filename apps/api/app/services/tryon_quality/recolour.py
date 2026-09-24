"""Hold a garment to the colour of its own product photo.

The image model's colour for the same garment moves between runs: one
render of an ivory farshi suit came back a warm yellow (b +11.9 against
the reference), another came back "pink-and-white" and was refused. The
shape, drape and embroidery were right both times — only the cast was
wrong, and that is measurable and correctable without asking for another
render.

So after the product's pixels are taken, their colour is pulled back
towards the product photo's own, in Lab, leaving L alone. Keeping
lightness untouched keeps the folds, shadows and embroidery exactly as
rendered; only hue and saturation move. The shift is capped, so a
genuinely different colour is never forced to match — a render that drew
a black dress instead of a white one still fails inspection, which is
what should happen.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.logging import logger

# Lab a/b units. Below the first, the cast is not worth touching; above
# the second, the render disagrees with the reference by more than a cast
# and correcting it would be inventing a match that isn't there.
_IGNORE_BELOW = 1.5
_MAX_SHIFT = 14.0
_STRENGTH = 0.85


def _median_ab(lab: np.ndarray, sel: np.ndarray) -> tuple[float, float]:
    return float(np.median(lab[..., 1][sel])) - 128, float(np.median(lab[..., 2][sel])) - 128


def product_colour(product: np.ndarray) -> tuple[float, float] | None:
    """The garment's own colour in its listing photo.

    Taken from the middle of the frame, which is where the product is in
    a listing photo, and from the mid-range of lightness — the darkest
    and lightest tenth are shadow and blown highlight (or the white
    background of a cut-out), and neither says anything about colour."""
    if product is None or product.size == 0:
        return None
    h, w = product.shape[:2]
    centre = product[int(h * 0.15) : int(h * 0.9), int(w * 0.22) : int(w * 0.78)]
    if centre.size == 0:
        return None
    lab = cv2.cvtColor(centre, cv2.COLOR_BGR2LAB).astype(np.float32)
    lightness = lab[..., 0]
    low, high = np.percentile(lightness, [10, 90])
    sel = (lightness >= low) & (lightness <= high)
    if sel.sum() < 200:
        return None
    return _median_ab(lab, sel)


def match_product_colour(
    image: np.ndarray, mask: np.ndarray, product: np.ndarray, *, name: str = ""
) -> np.ndarray:
    """`image` with the masked area's cast pulled towards `product`'s."""
    target = product_colour(product)
    sel = mask > 0.5
    if target is None or sel.sum() < 200:
        return image

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    drawn = _median_ab(lab, sel)
    shift = ((target[0] - drawn[0]) * _STRENGTH, (target[1] - drawn[1]) * _STRENGTH)
    if abs(shift[0]) < _IGNORE_BELOW and abs(shift[1]) < _IGNORE_BELOW:
        return image
    capped = (
        float(np.clip(shift[0], -_MAX_SHIFT, _MAX_SHIFT)),
        float(np.clip(shift[1], -_MAX_SHIFT, _MAX_SHIFT)),
    )

    weight = np.clip(mask, 0, 1)
    lab[..., 1] += capped[0] * weight
    lab[..., 2] += capped[1] * weight
    logger.info(
        "tryon_colour_pulled",
        item=name[:60],
        drawn=[round(v, 1) for v in drawn],
        reference=[round(v, 1) for v in target],
        shift=[round(v, 1) for v in capped],
    )
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
