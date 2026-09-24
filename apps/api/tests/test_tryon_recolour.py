"""Holding a garment to the colour of its own product photo.

The image model's colour for the same garment moves between runs — one
ivory suit came back yellow, another "pink-and-white" and was refused —
while the drape and embroidery were right both times. The cast is
measurable, so it is corrected rather than re-rendered and hoped for.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.services.tryon_quality.recolour import match_product_colour, product_colour


def _solid(bgr: tuple[int, int, int], size: int = 200) -> np.ndarray:
    return np.full((size, size, 3), bgr, np.uint8)


def _ab(image: np.ndarray, mask: np.ndarray | None = None) -> tuple[float, float]:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    sel = mask > 0.5 if mask is not None else np.ones(image.shape[:2], bool)
    return float(np.median(lab[..., 1][sel])) - 128, float(np.median(lab[..., 2][sel])) - 128


def _mask(shape: tuple[int, int], box: tuple[int, int, int, int]) -> np.ndarray:
    mask = np.zeros(shape, np.float32)
    y0, x0, y1, x1 = box
    mask[y0:y1, x0:x1] = 1.0
    return mask


IVORY = (225, 235, 240)  # BGR: warm off-white, the reference garment


def test_a_yellow_render_is_pulled_back_to_the_reference_ivory():
    product = _solid(IVORY)
    drawn = _solid((180, 235, 245))  # the same dress rendered too yellow
    mask = _mask(drawn.shape[:2], (40, 40, 160, 160))

    fixed = match_product_colour(drawn, mask, product)
    before = abs(_ab(drawn, mask)[1] - _ab(product)[1])
    after = abs(_ab(fixed, mask)[1] - _ab(product)[1])
    assert after < before / 2


def test_a_pink_render_is_pulled_back_too():
    product = _solid(IVORY)
    drawn = _solid((225, 215, 245))  # pink-and-white, the live refusal
    mask = _mask(drawn.shape[:2], (40, 40, 160, 160))

    fixed = match_product_colour(drawn, mask, product)
    before = abs(_ab(drawn, mask)[0] - _ab(product)[0])
    after = abs(_ab(fixed, mask)[0] - _ab(product)[0])
    assert after < before / 2


def test_nothing_outside_the_product_is_touched():
    """The face, hair and background are the person's photograph."""
    product = _solid(IVORY)
    drawn = _solid((180, 235, 245))
    mask = _mask(drawn.shape[:2], (40, 40, 160, 160))

    fixed = match_product_colour(drawn, mask, product)
    assert np.array_equal(fixed[:35, :35], drawn[:35, :35])
    assert np.array_equal(fixed[170:, 170:], drawn[170:, 170:])


def test_lightness_is_left_alone_so_folds_and_embroidery_survive():
    product = _solid(IVORY)
    drawn = _solid((180, 235, 245))
    mask = _mask(drawn.shape[:2], (40, 40, 160, 160))

    fixed = match_product_colour(drawn, mask, product)
    lightness = lambda img: cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0][mask > 0.5].mean()  # noqa: E731
    assert abs(lightness(fixed) - lightness(drawn)) < 3


def test_a_colour_that_is_already_right_is_not_touched():
    product = _solid(IVORY)
    drawn = _solid(IVORY)
    mask = _mask(drawn.shape[:2], (40, 40, 160, 160))
    assert np.array_equal(match_product_colour(drawn, mask, product), drawn)


def test_a_genuinely_wrong_colour_is_never_forced_to_match():
    """A render that drew the wrong garment must still fail inspection —
    the cap keeps this a correction, not a disguise."""
    product = _solid(IVORY)
    drawn = _solid((40, 40, 200))  # a red dress where an ivory one belongs
    mask = _mask(drawn.shape[:2], (40, 40, 160, 160))

    fixed = match_product_colour(drawn, mask, product)
    still_off = abs(_ab(fixed, mask)[0] - _ab(product)[0])
    assert still_off > 20  # nowhere near ivory, as it should be


def test_the_reference_colour_ignores_blown_highlights_and_shadow():
    """A listing photo is a garment on a white background under a hard
    light; neither extreme says anything about the garment's colour."""
    product = _solid(IVORY, size=300)
    product[:40] = (255, 255, 255)  # blown background
    product[-40:] = (10, 10, 10)  # deep shadow
    colour = product_colour(product)
    assert colour is not None
    assert abs(colour[0] - _ab(_solid(IVORY))[0]) < 2
    assert abs(colour[1] - _ab(_solid(IVORY))[1]) < 2
