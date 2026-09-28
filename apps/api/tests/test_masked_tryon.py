"""Try-on via real, API-level masked editing: each product drawn only
into a transparent window, everywhere else protected by the API itself
rather than reconstructed afterwards. Offline — downloads, description,
vision and the edit call are all faked; the mask image itself and the
region/ordering logic run for real."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

import asyncio

from app.models.enums import OutfitSlot
from app.services.face_restore import Box
from app.services.tryon_quality import masked
from app.services.tryon_quality.compose import Region, decode, encode_jpeg
from app.services.tryon_quality.judge import Verdict
from app.services.tryon_quality.masked import (
    LookItem,
    _mask_png,
    _mask_region,
    _order_of,
    _overlaps,
    _waves,
    render_masked_look,
)

GOOD = Verdict(9, 9, 8)
BAD = Verdict(4, 5, 6, ["wrong strap colour"], "make the bracelet silver steel like the reference")


def _photo(h=300, w=200) -> bytes:
    return encode_jpeg(np.full((h, w, 3), 220, np.uint8), 95)


@pytest.fixture
def fake_vision(monkeypatch):
    """No network: product download, description and a small item's body
    part are faked (a fixed region — where exactly doesn't matter to
    these tests); the test sets the inspector's verdicts, one per edit
    attempt."""
    verdicts: list[Verdict] = []

    async def download(url):  # noqa: ARG001
        return np.full((100, 100, 3), (200, 60, 20), np.uint8)

    async def describe(image, url, name):  # noqa: ARG001
        return f"{name} (described)"

    async def area_for(item, face, base):  # noqa: ARG001
        return Region(0.55, 0.55, 0.72, 0.66)  # a plausible wrist, say

    async def judge(product, before, after, region, description, small_item=False):  # noqa: ARG001
        return verdicts.pop(0)

    monkeypatch.setattr(masked, "_download", download)
    monkeypatch.setattr(masked, "describe_product", describe)
    monkeypatch.setattr(masked, "_area_for", area_for)
    monkeypatch.setattr(masked, "judge", judge)
    return verdicts


def _editor(calls: list):
    async def edit(person_png: bytes, mask_png: bytes, item: LookItem, hint) -> bytes:
        calls.append((item.name, hint.fix))
        return _photo()

    return edit


# --------------------------------------------------------------------- mask


def test_mask_png_is_transparent_only_inside_the_region():
    mask = _mask_png((100, 200), Region(0.25, 0.4, 0.75, 0.6))
    rgba = cv2.imdecode(np.frombuffer(mask, np.uint8), cv2.IMREAD_UNCHANGED)
    assert rgba.shape == (100, 200, 4)
    alpha = rgba[..., 3]
    assert (alpha[40:60, 50:150] == 0).all()  # inside the region: editable
    assert (alpha[:40, :] == 255).all()  # outside: protected
    assert (alpha[:, :50] == 255).all()
    assert (alpha[:, 150:] == 255).all()


# ------------------------------------------------------------------- order


def test_order_of_draws_garments_first_worn_items_last():
    items = [
        LookItem("x", OutfitSlot.WATCH, "watch"),
        LookItem("x", OutfitSlot.BAG, "bag"),
        LookItem("x", OutfitSlot.DRESS, "dress"),
        LookItem("x", OutfitSlot.SHOES, "shoes"),
    ]
    order = _order_of(items)
    assert [items[i].slot for i in order] == [OutfitSlot.DRESS, OutfitSlot.SHOES, OutfitSlot.BAG, OutfitSlot.WATCH]


def test_order_of_is_stable_for_items_of_the_same_kind():
    items = [LookItem("x", OutfitSlot.ACCESSORY, "earrings"), LookItem("x", OutfitSlot.ACCESSORY, "necklace")]
    assert _order_of(items) == [0, 1]


# ------------------------------------------------------------------ region


async def test_a_garments_mask_sits_below_the_chin_not_the_collar():
    face = Box(x=80, y=20, w=40, h=40)
    region = await _mask_region(LookItem("x", OutfitSlot.DRESS, "kameez"), face, np.zeros((300, 200, 3), np.uint8))
    assert region is not None
    # below the bottom of the face, not at its top
    assert region.y0 > (face.y + face.h) / 300
    assert region.x0 < 0.5 < region.x1  # wide enough to be centred on her


async def test_a_garments_mask_without_a_face_falls_back_to_the_plain_default():
    region = await _mask_region(LookItem("x", OutfitSlot.TOP, "shirt"), None, np.zeros((300, 200, 3), np.uint8))
    assert region == masked._MASK_REGION[OutfitSlot.TOP]


async def test_a_garments_mask_narrows_toward_her_on_a_wide_photo():
    """Live: on a full-body photo where she filled under half the frame
    width, the kameez's mask reached the fixed 0.03-0.97 ceiling on both
    sides — background metres away from her, a wedding hall's own décor —
    and the model re-staged the whole room. It should stop well short of
    the frame edge when her own face says there's no need to reach it."""
    face = Box(x=206, y=135, w=58, h=58)
    region = await _mask_region(LookItem("x", OutfitSlot.DRESS, "kameez"), face, np.zeros((668, 459, 3), np.uint8))
    assert region is not None
    assert region.x0 > masked._MASK_REGION[OutfitSlot.DRESS].x0  # tighter than the fixed ceiling
    assert region.x1 < masked._MASK_REGION[OutfitSlot.DRESS].x1
    assert region.x0 < 0.5 < region.x1  # still centred on her


async def test_a_garments_mask_never_widens_past_the_fixed_ceiling():
    # a close, cropped-in face makes the face-relative window huge —
    # nothing here should ever reach past the slot's own fixed bounds
    face = Box(x=60, y=40, w=150, h=150)
    region = await _mask_region(LookItem("x", OutfitSlot.DRESS, "kameez"), face, np.zeros((300, 200, 3), np.uint8))
    fixed = masked._MASK_REGION[OutfitSlot.DRESS]
    assert region.x0 == fixed.x0 and region.x1 == fixed.x1


async def test_a_non_garment_defers_to_the_existing_body_part_lookup(monkeypatch):
    called = {}

    async def fake_area_for(item, face, base):  # noqa: ARG001
        called["item"] = item.name
        return Region(0.4, 0.6, 0.6, 0.7)

    monkeypatch.setattr(masked, "_area_for", fake_area_for)
    region = await _mask_region(LookItem("x", OutfitSlot.WATCH, "Bulova"), None, np.zeros((10, 10, 3), np.uint8))
    assert called["item"] == "Bulova"
    assert region == Region(0.4, 0.6, 0.6, 0.7)


# -------------------------------------------------------------- orchestration

ITEMS = [
    LookItem("https://img.example/kameez.jpg", OutfitSlot.DRESS, "Shalwar Kameez"),
    LookItem("https://img.example/watch.jpg", OutfitSlot.WATCH, "Bulova Blue Dial Watch"),
]


async def test_a_good_edit_is_accepted_first_time(fake_vision):
    fake_vision.extend([GOOD, GOOD])
    calls: list = []
    image, reports = await render_masked_look(_photo(), ITEMS, _editor(calls), retries=1)
    assert len(calls) == 2  # one edit per item, no retries needed
    assert [r.attempts for r in reports] == [1, 1]
    assert all(r.verdict == GOOD for r in reports)
    assert image[:2] == b"\xff\xd8"


async def test_a_failed_inspection_is_retried_with_the_fix(fake_vision):
    fake_vision.extend([BAD, GOOD])
    calls: list = []
    _, reports = await render_masked_look(_photo(), [ITEMS[1]], _editor(calls), retries=1)
    assert len(calls) == 2
    # the inspector's own words reach the second attempt as raw text —
    # openai_image.masked_prompt() is the one place that labels it
    assert calls[0][1] == "" and "wrong strap colour" in calls[1][1]
    assert reports[0].verdict == GOOD


async def test_a_near_miss_is_kept_without_spending_a_retry(fake_vision):
    close = Verdict(6, 5, 6)  # one point under the 7/6 bar on every axis
    fake_vision.append(close)
    calls: list = []
    _, reports = await render_masked_look(
        _photo(), [ITEMS[1]], _editor(calls), retries=1, min_product=7, min_other=6
    )
    assert len(calls) == 1  # no second attempt bought for a point nobody would see
    assert reports[0].verdict == close
    assert any("near miss" in h for h in reports[0].history)


async def test_out_of_retries_ships_the_best_attempt_rather_than_nothing(fake_vision):
    fake_vision.extend([BAD, BAD])
    calls: list = []
    image, reports = await render_masked_look(_photo(), [ITEMS[1]], _editor(calls), retries=1)
    assert len(calls) == 2  # one attempt, one retry, then ship
    assert reports[0].verdict == BAD
    assert reports[0].box is not None
    assert image[:2] == b"\xff\xd8"  # the customer still gets a photo


async def test_an_item_with_no_findable_region_is_skipped_not_failed(fake_vision, monkeypatch):
    async def no_region(item, face, base):  # noqa: ARG001
        return None

    monkeypatch.setattr(masked, "_area_for", no_region)
    calls: list = []
    image, reports = await render_masked_look(_photo(), [ITEMS[1]], _editor(calls), retries=1)
    assert calls == []  # never asked the model to edit anything
    assert reports[0].box is None
    assert "couldn't find" in reports[0].history[0]
    assert image[:2] == b"\xff\xd8"  # still a valid photo — just without this item


async def test_a_failed_edit_call_does_not_lose_the_rest_of_the_look(fake_vision):
    fake_vision.append(GOOD)  # only the watch gets judged — the kameez's edit raises first

    calls: list = []

    async def flaky_edit(person_png, mask_png, item: LookItem, hint):  # noqa: ARG001
        if item.slot == OutfitSlot.DRESS:
            raise RuntimeError("the API had a bad moment")
        calls.append(item.name)
        return _photo()

    _, reports = await render_masked_look(_photo(), ITEMS, flaky_edit, retries=0)
    dress_report, watch_report = reports
    assert dress_report.box is None and "failed" in dress_report.history[0]
    assert watch_report.verdict == GOOD  # the watch still went through


async def test_each_items_box_is_the_exact_mask_used_not_a_recovered_guess(fake_vision):
    fake_vision.extend([GOOD, GOOD])
    _, reports = await render_masked_look(_photo(), ITEMS, _editor([]), retries=1)
    dress_report, watch_report = reports
    assert dress_report.box == masked._MASK_REGION[OutfitSlot.DRESS]  # no face in this blank photo: the plain default
    assert watch_report.box == Region(0.55, 0.55, 0.72, 0.66)  # exactly what _area_for said, not a guess


# --------------------------------------------------------------- the clamp


async def test_a_hand_item_reaching_above_the_shoulder_is_pulled_back_down(monkeypatch):
    """Live: asked for "the person's hands, forearms and shoulders", the
    body-part lookup returned a box starting 2.5% down the photo — the
    top of her head — and the bag edit drew a scarf into it, over her
    face. The same query returned a sensible, shoulder-height box on a
    different run: this is the backstop for whichever one it gives, not
    a fix to the lookup itself."""

    async def bad_area_for(item, face, base):  # noqa: ARG001
        return Region(0.2, 0.02, 0.8, 0.6)  # reaches the top of the frame

    monkeypatch.setattr(masked, "_area_for", bad_area_for)
    face = Box(x=400, y=90, w=180, h=180)
    region = await _mask_region(LookItem("x", OutfitSlot.BAG, "Tote Bag"), face, np.zeros((1536, 1024, 3), np.uint8))

    assert region is not None
    assert region.y0 > (face.y + face.h) / 1536  # never reaches above the shoulder
    assert region.x0 == 0.2 and region.x1 == 0.8  # only the vertical reach was corrected


async def test_a_hand_item_already_below_the_shoulder_is_left_alone(monkeypatch):
    async def sensible_area_for(item, face, base):  # noqa: ARG001
        return Region(0.2, 0.5, 0.8, 0.7)

    monkeypatch.setattr(masked, "_area_for", sensible_area_for)
    face = Box(x=400, y=90, w=180, h=180)
    region = await _mask_region(LookItem("x", OutfitSlot.WATCH, "Watch"), face, np.zeros((1536, 1024, 3), np.uint8))
    assert region == Region(0.2, 0.5, 0.8, 0.7)


async def test_a_neck_or_head_item_is_never_clamped_away_from_the_face(monkeypatch):
    """A necklace or a hairband legitimately needs to reach up to the ears
    or down from the chin — the clamp that protects a bag from the face
    must not also stop these from reaching it. (Not earrings or a tikka
    here — those now get their own geometric window and never reach
    _area_for() at all; see the forehead/ear tests below.)"""

    async def near_the_face(item, face, base):  # noqa: ARG001
        return Region(0.3, 0.05, 0.7, 0.3)  # genuinely up near the head, for a hairband

    monkeypatch.setattr(masked, "_area_for", near_the_face)
    face = Box(x=400, y=90, w=180, h=180)
    region = await _mask_region(
        LookItem("x", OutfitSlot.ACCESSORY, "Bridal Hairband"), face, np.zeros((1536, 1024, 3), np.uint8)
    )
    assert region == Region(0.3, 0.05, 0.7, 0.3)  # untouched


async def test_eyewear_never_asks_the_body_part_lookup_at_all(monkeypatch):
    """Real bug: asked live for oversized sunglasses, the body-part lookup
    returned a window nearly 3 face-widths wide and 2 face-heights tall —
    most of the face, not a band across the eyes — with nothing checking
    it, because every worn-on-head item is exempted from the shoulder
    clamp (they legitimately reach the head) and eyewear inherited that
    exemption with no clamp of its own. The render came back with a
    different face. Eyewear's real position doesn't need a guess: it
    sits on the face at a fixed place relative to it, so this bypasses
    the lookup entirely rather than trusting a number proven unreliable."""

    async def never_called(item, face, base):  # noqa: ARG001
        raise AssertionError("eyewear must not reach the body-part lookup at all")

    monkeypatch.setattr(masked, "_area_for", never_called)
    face = Box(x=206, y=135, w=58, h=58)
    region = await _mask_region(
        LookItem("x", OutfitSlot.ACCESSORY, "Oversized Square Sunglasses"), face, np.zeros((668, 459, 3), np.uint8)
    )
    assert region is not None
    # a tight band across the eyes, not most of the face
    assert region.y1 - region.y0 < 0.1
    assert region.x0 < 0.5 < region.x1  # centred on her
    assert region.y0 > face.y / 668  # starts at or below the top of the face, not above it


async def test_eyewear_matches_by_name_regardless_of_slot():
    face = Box(x=206, y=135, w=58, h=58)
    for name in ["Vintage Round Sunglasses", "Blue Light Glasses", "Ski Goggles"]:
        region = await _mask_region(LookItem("x", OutfitSlot.OTHER, name), face, np.zeros((668, 459, 3), np.uint8))
        assert region is not None and region.y1 - region.y0 < 0.1


async def test_a_tikka_and_earrings_never_reach_the_body_part_lookup_either(monkeypatch):
    """Real bug: a maang tikka and a pair of earrings both fell through
    to pipeline._plausible_area()'s one generic worn_on_head() box —
    the exact same window a hairband or sunglasses got, reaching from
    above the eyebrows to well past the chin. A tikka photographed as
    part of a matching necklace-and-earrings set had, inside that much
    room, both the space and the visual reference to draw a necklace
    that was never asked for. Tikka and earrings now get their own
    geometry, computed directly, same as eyewear — never the lookup."""

    async def never_called(item, face, base):  # noqa: ARG001
        raise AssertionError("tikka/earrings must not reach the body-part lookup")

    monkeypatch.setattr(masked, "_area_for", never_called)
    face = Box(x=206, y=135, w=58, h=58)
    base = np.zeros((668, 459, 3), np.uint8)

    tikka = await _mask_region(LookItem("x", OutfitSlot.ACCESSORY, "Kundan Maang Tikka"), face, base)
    assert tikka is not None
    assert tikka.y1 <= (face.y + 0.3 * face.h) / 668 + 1e-9  # stays on the forehead, not past the brow
    assert tikka.x0 < 0.5 < tikka.x1

    earrings = await _mask_region(LookItem("x", OutfitSlot.ACCESSORY, "Jhumka Earrings"), face, base)
    assert earrings is not None
    assert earrings.y0 >= (face.y + 0.15 * face.h) / 668 - 1e-9  # starts at the ear line, not the forehead
    # tighter than the old shared box's bottom (0.6 face-heights below
    # the chin) — that extra reach toward the neck/chest is what left
    # room for a hallucinated necklace beside the tikka
    assert earrings.y1 < (face.y + 1.6 * face.h) / 668


# --------------------------------------------------------------------- waves


def test_overlaps_is_true_for_crossing_regions_and_false_with_a_gap():
    assert _overlaps(Region(0.0, 0.0, 0.5, 0.5), Region(0.4, 0.4, 0.9, 0.9))
    assert not _overlaps(Region(0.0, 0.0, 0.3, 0.3), Region(0.6, 0.6, 0.9, 0.9))


def test_overlaps_keeps_a_margin_around_a_bare_touch():
    # sharing an exact edge isn't a gap: the API's own blend at the
    # boundary is real, so two windows that just meet still count as
    # overlapping rather than being trusted to draw in the same round
    assert _overlaps(Region(0.0, 0.0, 0.5, 1.0), Region(0.5, 0.0, 1.0, 1.0))


def test_waves_batches_non_overlapping_steps_together():
    regions = [Region(0.0, 0.0, 0.3, 0.3), Region(0.6, 0.6, 0.9, 0.9), Region(0.0, 0.6, 0.3, 0.9)]
    assert _waves([0, 1, 2], regions) == [[0, 1, 2]]  # none of the three touch


def test_waves_separates_steps_whose_windows_cross():
    # step 0 is a dress-sized box; step 1 sits inside it and must wait
    regions = [Region(0.0, 0.0, 1.0, 1.0), Region(0.4, 0.4, 0.6, 0.6)]
    assert _waves([0, 1], regions) == [[0], [1]]


def test_waves_lets_a_third_item_join_whichever_wave_it_fits():
    # 0 and 1 collide (both waves must stay apart); 2 fits in neither
    # 0's wave nor a spot alone if it also collides with 1 only — it
    # should land with 0, the earliest wave it doesn't cross
    regions = [Region(0.0, 0.0, 0.5, 0.5), Region(0.4, 0.4, 0.9, 0.9), Region(0.0, 0.6, 0.5, 1.0)]
    assert _waves([0, 1, 2], regions) == [[0, 2], [1]]


# ------------------------------------------------------- parallel rendering


async def test_non_overlapping_items_draw_in_the_same_round(monkeypatch):
    """If these ran one after another rather than together, the first call
    would block forever on an event only the second call sets — this test
    times out rather than passing if the pipeline regresses to serial."""
    entered: list[str] = []
    second_arrived = asyncio.Event()

    async def area_for(item, face, base):  # noqa: ARG001
        return {"Watch": Region(0.0, 0.0, 0.3, 0.3), "Bag": Region(0.6, 0.6, 0.9, 0.9)}[item.name]

    async def download(url):  # noqa: ARG001
        return np.zeros((10, 10, 3), np.uint8)

    async def describe(image, url, name):  # noqa: ARG001
        return name

    async def judge_ok(product, before, after, region, description, small_item=False):  # noqa: ARG001
        return GOOD

    async def edit(person_png, mask_png, item, hint):  # noqa: ARG001
        entered.append(item.name)
        if len(entered) == 1:
            await second_arrived.wait()  # only released once BOTH have started
        else:
            second_arrived.set()
        return _photo()

    monkeypatch.setattr(masked, "_area_for", area_for)
    monkeypatch.setattr(masked, "_download", download)
    monkeypatch.setattr(masked, "describe_product", describe)
    monkeypatch.setattr(masked, "judge", judge_ok)

    items = [LookItem("x", OutfitSlot.WATCH, "Watch"), LookItem("x", OutfitSlot.BAG, "Bag")]
    _, reports = await asyncio.wait_for(render_masked_look(_photo(), items, edit, retries=0), timeout=2)
    assert sorted(entered) == ["Bag", "Watch"]
    assert all(r.verdict == GOOD for r in reports)


async def test_a_parallel_rounds_result_takes_each_items_own_window_only(monkeypatch):
    async def area_for(item, face, base):  # noqa: ARG001
        return {"Watch": Region(0.0, 0.0, 0.4, 0.4), "Bag": Region(0.6, 0.6, 1.0, 1.0)}[item.name]

    async def download(url):  # noqa: ARG001
        return np.zeros((10, 10, 3), np.uint8)

    async def describe(image, url, name):  # noqa: ARG001
        return name

    async def judge_ok(product, before, after, region, description, small_item=False):  # noqa: ARG001
        return GOOD

    colours = {"Watch": (0, 0, 255), "Bag": (255, 0, 0)}

    async def edit(person_png, mask_png, item, hint):  # noqa: ARG001
        return encode_jpeg(np.full((300, 200, 3), colours[item.name], np.uint8), 95)

    monkeypatch.setattr(masked, "_area_for", area_for)
    monkeypatch.setattr(masked, "_download", download)
    monkeypatch.setattr(masked, "describe_product", describe)
    monkeypatch.setattr(masked, "judge", judge_ok)

    items = [LookItem("x", OutfitSlot.WATCH, "Watch"), LookItem("x", OutfitSlot.BAG, "Bag")]
    image, _ = await render_masked_look(_photo(), items, edit, retries=0)

    def close(pixel, expected):
        return all(abs(int(a) - b) <= 6 for a, b in zip(pixel, expected))  # allows for JPEG round-trip

    out = decode(image)
    assert close(out[20, 20], colours["Watch"])  # inside the watch's own window
    assert close(out[250, 150], colours["Bag"])  # inside the bag's own window
    assert close(out[150, 100], (220, 220, 220))  # untouched: the original grey
