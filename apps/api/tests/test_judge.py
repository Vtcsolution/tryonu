"""The deterministic, product-agnostic verification gates added alongside
the VLM judge: a colour mismatch or a region that never changed must fail
regardless of what the vision model says about it — a VLM graded in
isolation can be talked into a generous score by a confident-looking
render even when it's the wrong colour or was never drawn at all."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.tryon_quality import judge as judge_module
from app.services.tryon_quality.compose import Region
from app.services.tryon_quality.judge import (
    _COLOR_FAIL_DELTA_E,
    _delta_e_ciede2000,
    _dominant_lab,
    color_mismatch,
    judge,
    region_was_touched,
)


def _solid(color_bgr: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> np.ndarray:
    return np.full((*size, 3), color_bgr, dtype=np.uint8)


def _studio_photo(product_bgr: tuple[int, int, int], size: tuple[int, int] = (300, 300)) -> np.ndarray:
    """A product reference photo: a colourful item on a white studio
    background — most retailer photos look like this."""
    img = np.full((*size, 3), (245, 245, 245), dtype=np.uint8)
    h, w = size
    img[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = product_bgr
    return img


# --------------------------------------------------------------- CIEDE2000


def test_identical_colours_have_zero_distance():
    lab = _dominant_lab(_solid((60, 90, 180)))  # some arbitrary BGR
    assert _delta_e_ciede2000(lab, lab) == pytest.approx(0.0, abs=1e-6)


def test_red_and_blue_are_clearly_different():
    red = _dominant_lab(_solid((0, 0, 255)))  # BGR: pure red
    blue = _dominant_lab(_solid((255, 0, 0)))  # BGR: pure blue
    assert _delta_e_ciede2000(red, blue) > 30  # nowhere near "same colour, different light"


def test_two_close_shades_of_the_same_colour_are_small():
    a = _dominant_lab(_solid((40, 40, 200)))
    b = _dominant_lab(_solid((55, 55, 215)))  # a slightly lighter version of the same red
    assert _delta_e_ciede2000(a, b) < _COLOR_FAIL_DELTA_E


# ------------------------------------------------------------- dominant_lab


def test_dominant_lab_ignores_a_white_studio_background():
    """The whole point: a product photo is mostly backdrop by area, but
    the colour estimate must come from the product, not the white wall
    behind it."""
    white_only = _dominant_lab(np.full((300, 300, 3), (245, 245, 245), dtype=np.uint8))
    red_product = _dominant_lab(_studio_photo((0, 0, 220)))  # red product, 1/4 the frame, white around it
    # the red product's own estimate must land far from a pure-white estimate,
    # even though white pixels are the majority of that image
    assert _delta_e_ciede2000(white_only, red_product) > 30


# --------------------------------------------------------- color_mismatch


def test_color_mismatch_passes_the_true_products_own_colour():
    product = _studio_photo((0, 0, 220))  # a red product on white
    result_crop = _solid((10, 10, 200))  # the rendered item: also red
    assert color_mismatch(result_crop, product) < _COLOR_FAIL_DELTA_E


def test_color_mismatch_fails_a_recoloured_product():
    """The live job's exact case: the rendered item's colour drifted to
    resemble a different selected product's colour instead of its own."""
    red_product = _studio_photo((0, 0, 220))
    white_result = _solid((235, 235, 235))  # rendered white instead of red
    assert color_mismatch(white_result, red_product) >= _COLOR_FAIL_DELTA_E


# ------------------------------------------------------------ region_was_touched


def test_an_untouched_region_is_not_touched():
    img = _solid((120, 140, 160))
    assert not region_was_touched(img, img.copy())


def test_a_genuinely_redrawn_region_is_touched():
    before = _solid((120, 140, 160))
    after = _solid((20, 40, 220))  # a large, clear colour change over the whole crop
    assert region_was_touched(before, after)


def test_minor_resampling_noise_alone_does_not_count_as_touched():
    """This is the exact trap judge.py's own module docstring warns about:
    a plain whole-image diff reads 20-50% "changed" on a visually-correct
    render from resolution/re-encoding differences alone. A small amount
    of uniform per-pixel jitter must not clear the bar on its own."""
    rng = np.random.default_rng(3)
    before = np.full((200, 200, 3), 150, dtype=np.uint8)
    noise = rng.integers(-4, 5, before.shape, dtype=np.int16)
    after = np.clip(before.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    assert not region_was_touched(before, after)


def test_touched_handles_a_resized_after_crop():
    before = _solid((120, 140, 160), size=(200, 200))
    after = _solid((20, 40, 220), size=(140, 140))  # model's own output resolution differs
    assert region_was_touched(before, after)


# --------------------------------------------------------------- judge() itself


@pytest.fixture
def fake_vlm(monkeypatch):
    """judge() still asks the VLM — these tests fix what it answers, to
    prove the deterministic checks override a generous VLM score, not
    replace asking it."""
    answer = {"product_match": 9, "worn_correctly": 9, "realism": 9, "issues": [], "fix": ""}

    async def fake_ask_json(instructions, content, **kw):  # noqa: ARG001
        return dict(answer)

    monkeypatch.setattr(judge_module, "ask_json", fake_ask_json)
    return answer


async def test_a_missing_product_fails_even_if_the_vlm_is_generous(fake_vlm):
    region = Region(0.25, 0.25, 0.75, 0.75)
    base = np.full((200, 200, 3), (150, 150, 150), dtype=np.uint8)
    product = _studio_photo((0, 0, 220))
    verdict = await judge(product, base, base.copy(), region, "a red item")
    assert verdict.product_match == 0.0
    assert "never drawn" in verdict.issues[0]


async def test_a_recoloured_product_fails_even_if_the_vlm_is_generous(fake_vlm):
    region = Region(0.0, 0.0, 1.0, 1.0)
    before = np.full((200, 200, 3), (150, 150, 150), dtype=np.uint8)
    after = np.full((200, 200, 3), (235, 235, 235), dtype=np.uint8)  # drawn, but white not red
    product = _studio_photo((0, 0, 220))  # the real product is red
    verdict = await judge(product, before, after, region, "a red item")
    assert verdict.product_match <= 3.0
    assert "colour" in verdict.issues[0]


async def test_a_correctly_applied_product_passes(fake_vlm):
    region = Region(0.0, 0.0, 1.0, 1.0)
    before = np.full((200, 200, 3), (150, 150, 150), dtype=np.uint8)
    after = np.full((200, 200, 3), (10, 10, 200), dtype=np.uint8)  # drawn, and the right colour (red)
    product = _studio_photo((0, 0, 220))
    verdict = await judge(product, before, after, region, "a red item")
    assert verdict.product_match == 9.0  # the VLM's own score survives — neither gate fired
    assert verdict.passes(7.0, 6.0)
