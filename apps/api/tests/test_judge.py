"""The deterministic, product-agnostic verification gates added alongside
the VLM judge: a colour mismatch or a region that never changed must fail
regardless of what the vision model says about it — a VLM graded in
isolation can be talked into a generous score by a confident-looking
render even when it's the wrong colour or was never drawn at all.

product_cutout_mask() (real background removal, see cutout.py) is mocked
throughout: this suite runs with zero network access, and the real model
is tested for real in test_cutout.py instead. What's under test here is
colour_mismatch()'s own logic given a mask, not the segmentation itself."""

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
    has_seam,
    judge,
    region_was_touched,
    seam_score,
)

PRODUCT_URL = "https://img.example/product.jpg"


def _solid(color_bgr: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> np.ndarray:
    return np.full((*size, 3), color_bgr, dtype=np.uint8)


def _studio_photo(product_bgr: tuple[int, int, int], size: tuple[int, int] = (300, 300)) -> np.ndarray:
    """A product reference photo: an item on a white studio background —
    most retailer photos look like this. Returns the photo and the exact
    foreground mask a real cutout model would be expected to produce for
    it, so tests can mock product_cutout_mask() with ground truth rather
    than guessing at what real segmentation would return."""
    img = np.full((*size, 3), (245, 245, 245), dtype=np.uint8)
    h, w = size
    mask = np.zeros((h, w), dtype=np.uint8)
    img[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = product_bgr
    mask[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = 255
    return img, mask


@pytest.fixture
def mock_cutout(monkeypatch):
    """Returns the exact mask to serve next; defaults to None (no mock —
    tests that don't need a cutout, like region_was_touched, never
    trigger one)."""
    masks: dict[str, np.ndarray] = {}

    def fake_cutout(image, image_url):
        return masks.get(image_url, np.full(image.shape[:2], 255, dtype=np.uint8))

    monkeypatch.setattr(judge_module, "product_cutout_mask", fake_cutout)
    return masks


# --------------------------------------------------------------- CIEDE2000


def test_identical_colours_have_zero_distance():
    lab = _dominant_lab(_solid((60, 90, 180)))
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


def test_dominant_lab_uses_only_the_masked_pixels():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:50] = (0, 0, 220)  # red half
    img[50:] = (220, 0, 0)  # blue half
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[:50] = 255  # only the red half is "foreground"
    red = _dominant_lab(_solid((0, 0, 220)))
    assert _delta_e_ciede2000(_dominant_lab(img, mask), red) < 1.0


def test_dominant_lab_with_no_mask_uses_every_pixel():
    """The result crop is already cropped to the item's own region — no
    further masking is needed or applied there."""
    img = _solid((10, 20, 200))
    assert _dominant_lab(img, None) == _dominant_lab(img)


# --------------------------------------------------------- color_mismatch
#
# Every colour family the live job's bug class could hide in: a product
# that itself looks like a studio backdrop (white/cream/silver) is
# exactly what the old brightness-based heuristic silently excluded from
# its own colour estimate.


@pytest.mark.parametrize(
    "product_bgr,correct_bgr,wrong_bgr",
    [
        pytest.param((235, 235, 235), (230, 230, 230), (10, 10, 200), id="white_on_white"),
        pytest.param((210, 230, 235), (205, 225, 230), (10, 10, 200), id="cream"),
        pytest.param((200, 200, 200), (195, 195, 195), (10, 10, 200), id="silver_grey"),
        pytest.param((20, 20, 20), (25, 25, 25), (230, 230, 230), id="black"),
        pytest.param((40, 160, 40), (50, 170, 50), (10, 10, 200), id="multicolour_green"),
        pytest.param((10, 10, 200), (15, 15, 210), (40, 160, 40), id="multicolour_red"),
    ],
)
def test_color_mismatch_across_product_colour_families(mock_cutout, product_bgr, correct_bgr, wrong_bgr):
    product, mask = _studio_photo(product_bgr)
    mock_cutout[PRODUCT_URL] = mask

    correct_render = _solid(correct_bgr)
    wrong_render = _solid(wrong_bgr)
    assert color_mismatch(correct_render, product, PRODUCT_URL) < _COLOR_FAIL_DELTA_E
    assert color_mismatch(wrong_render, product, PRODUCT_URL) >= _COLOR_FAIL_DELTA_E


def test_color_mismatch_fails_the_live_jobs_exact_case(mock_cutout):
    """The live job: a WHITE product's rendered colour drifted to RED
    (another selected product's colour bled into this item's region)."""
    white_product, mask = _studio_photo((235, 235, 235))
    mock_cutout[PRODUCT_URL] = mask
    red_result = _solid((10, 10, 200))
    assert color_mismatch(red_result, white_product, PRODUCT_URL) >= _COLOR_FAIL_DELTA_E


def test_color_mismatch_fails_the_reverse_direction_too(mock_cutout):
    """The same bug class running the other way: a RED product rendered
    WHITE. Colour mismatch must not have a blind spot in either direction."""
    red_product, mask = _studio_photo((0, 0, 220))
    mock_cutout[PRODUCT_URL] = mask
    white_result = _solid((235, 235, 235))
    assert color_mismatch(white_result, red_product, PRODUCT_URL) >= _COLOR_FAIL_DELTA_E


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


# ------------------------------------------------------------------- seam_score
#
# A generic, product-agnostic signal for a hard paste boundary: elevated
# local edge strength in a ring that traces the pasted region's own
# rectangle, well above its immediate surroundings. These tests prove the
# bare signal fires on an obvious hard paste and stays quiet on a smooth
# photo; judge()'s own use of it as a real fail gate (_SEAM_FAIL_RATIO) is
# tested separately, below, now that real production renders calibrated it.


def _smooth_gradient(size: tuple[int, int] = (240, 240)) -> np.ndarray:
    """A photo-like image with no hard edges anywhere: a smooth diagonal
    gradient, repeated across all three channels."""
    h, w = size
    x = np.linspace(0, 255, w, dtype=np.float32)
    y = np.linspace(0, 255, h, dtype=np.float32)
    plane = (x[None, :] + y[:, None]) / 2
    return np.repeat(plane[:, :, None], 3, axis=2).astype(np.uint8)


def _hard_paste(image: np.ndarray, region: Region, color_bgr: tuple[int, int, int]) -> np.ndarray:
    """A straight rectangle cut, unblended — exactly the kind of paste
    _paste() in masked.py exists to avoid, reproduced here on purpose."""
    out = image.copy()
    h, w = image.shape[:2]
    x0, y0, x1, y1 = region.pixels(w, h)
    out[y0:y1, x0:x1] = color_bgr
    return out


def test_a_hard_unblended_paste_is_flagged():
    base = _smooth_gradient()
    region = Region(0.3, 0.3, 0.7, 0.7)
    seamed = _hard_paste(base, region, (10, 10, 200))  # sharply different from the gradient around it
    assert has_seam(seamed, region)


def test_an_untouched_smooth_photo_is_not_flagged():
    base = _smooth_gradient()
    region = Region(0.3, 0.3, 0.7, 0.7)
    assert not has_seam(base, region)


def test_a_region_that_continues_the_surrounding_gradient_is_not_flagged():
    """A "paste" whose own content happens to match its surroundings
    smoothly — the ideal, well-blended case — must not be flagged just for
    having a region at all."""
    base = _smooth_gradient()
    region = Region(0.3, 0.3, 0.7, 0.7)
    h, w = base.shape[:2]
    x0, y0, x1, y1 = region.pixels(w, h)
    pasted = base.copy()
    pasted[y0:y1, x0:x1] = base[y0:y1, x0:x1]  # the same smooth content, not a different one
    assert not has_seam(pasted, region)


def test_seam_score_returns_zero_when_the_region_touches_the_photo_edge():
    """No "outside the box" band exists when the box runs to the frame's
    own edge — nothing to compare the boundary ring against, so this
    returns a neutral 0.0 rather than a false signal."""
    base = _smooth_gradient()
    region = Region(0.0, 0.0, 0.3, 0.3)  # touches the top-left corner of the photo
    assert seam_score(base, region) == 0.0


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


async def test_a_missing_product_fails_even_if_the_vlm_is_generous(fake_vlm, mock_cutout):
    region = Region(0.25, 0.25, 0.75, 0.75)
    base = np.full((200, 200, 3), (150, 150, 150), dtype=np.uint8)
    product, mask = _studio_photo((0, 0, 220))
    mock_cutout[PRODUCT_URL] = mask
    verdict = await judge(product, base, base.copy(), region, "a red item", False, PRODUCT_URL)
    assert verdict.product_match == 0.0
    assert "never drawn" in verdict.issues[0]


async def test_a_recoloured_product_fails_even_if_the_vlm_is_generous(fake_vlm, mock_cutout):
    region = Region(0.0, 0.0, 1.0, 1.0)
    before = np.full((200, 200, 3), (150, 150, 150), dtype=np.uint8)
    after = np.full((200, 200, 3), (235, 235, 235), dtype=np.uint8)  # drawn, but white not red
    product, mask = _studio_photo((0, 0, 220))  # the real product is red
    mock_cutout[PRODUCT_URL] = mask
    verdict = await judge(product, before, after, region, "a red item", False, PRODUCT_URL)
    assert verdict.product_match <= 3.0
    assert "colour" in verdict.issues[0]


async def test_a_white_product_rendered_red_fails_even_if_the_vlm_is_generous(fake_vlm, mock_cutout):
    """The live job, end to end through judge(): a white product's region
    came out red (another item's colour bled in). The dedicated unit test
    is test_color_mismatch_fails_the_live_jobs_exact_case; this proves the
    same failure survives through the full judge() call, not just the
    bare colour_mismatch() function."""
    region = Region(0.0, 0.0, 1.0, 1.0)
    before = np.full((200, 200, 3), (150, 150, 150), dtype=np.uint8)
    after = np.full((200, 200, 3), (10, 10, 200), dtype=np.uint8)  # drawn, but red not white
    product, mask = _studio_photo((235, 235, 235))  # the real product is white
    mock_cutout[PRODUCT_URL] = mask
    verdict = await judge(product, before, after, region, "a white item", False, PRODUCT_URL)
    assert verdict.product_match <= 3.0
    assert "colour" in verdict.issues[0]


async def test_a_correctly_applied_product_passes(fake_vlm, mock_cutout):
    region = Region(0.0, 0.0, 1.0, 1.0)
    before = np.full((200, 200, 3), (150, 150, 150), dtype=np.uint8)
    after = np.full((200, 200, 3), (10, 10, 200), dtype=np.uint8)  # drawn, and the right colour (red)
    product, mask = _studio_photo((0, 0, 220))
    mock_cutout[PRODUCT_URL] = mask
    verdict = await judge(product, before, after, region, "a red item", False, PRODUCT_URL)
    assert verdict.product_match == 9.0  # the VLM's own score survives — neither gate fired
    assert verdict.passes(7.0, 6.0)


async def test_a_white_product_correctly_applied_passes(fake_vlm, mock_cutout):
    """The exact regression this request started from: a white/cream/
    silver product must not disappear from its own colour measurement."""
    region = Region(0.0, 0.0, 1.0, 1.0)
    before = np.full((200, 200, 3), (120, 130, 140), dtype=np.uint8)
    after = np.full((200, 200, 3), (230, 230, 230), dtype=np.uint8)  # drawn, correctly white
    product, mask = _studio_photo((235, 235, 235))  # a white product, white backdrop
    mock_cutout[PRODUCT_URL] = mask
    verdict = await judge(product, before, after, region, "a white item", False, PRODUCT_URL)
    assert verdict.product_match == 9.0
    assert verdict.passes(7.0, 6.0)


async def test_a_hard_paste_boundary_fails_even_if_the_vlm_is_generous(fake_vlm, mock_cutout):
    """The real production incident this gate exists for: a small item's
    own window came back with a flat, unblended patch at its own edge —
    reported live as a black box over the face — that the VLM alone judged
    fine. The patch's own colour matches the product exactly, so only the
    seam gate (not color_mismatch) can be what fails this."""
    region = Region(0.3, 0.3, 0.7, 0.7)
    before = _smooth_gradient()
    after = _hard_paste(before, region, (10, 10, 10))
    product, mask = _studio_photo((10, 10, 10))
    mock_cutout[PRODUCT_URL] = mask
    verdict = await judge(product, before, after, region, "a dark item", False, PRODUCT_URL)
    assert verdict.product_match <= 3.0
    assert "seam" in verdict.issues[0]
