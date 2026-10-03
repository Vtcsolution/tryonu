"""The end-of-look check, offline. The vision call is replaced by a fake answer."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from app.services.tryon_direct import final_check as fc
from app.services.tryon_direct.final_check import REVIEW_REQUIRED, VERIFIED, final_check, region_still_present


def _png(rects: list[tuple[tuple[float, float, float, float], tuple[int, int, int]]]) -> bytes:
    img = Image.new("RGB", (400, 500), (180, 160, 140))
    draw = ImageDraw.Draw(img)
    for (x0, y0, x1, y1), colour in rects:
        draw.rectangle([int(x0 * 400), int(y0 * 500), int(x1 * 400), int(y1 * 500)], fill=colour)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


TOP = (0.3, 0.3, 0.7, 0.55)
SHOES = (0.35, 0.85, 0.65, 0.95)
RED, BLUE, GREEN = (200, 30, 40), (30, 60, 200), (30, 160, 60)

PERSON = _png([])
STEP_1 = _png([(TOP, RED)])
STEP_2 = _png([(TOP, RED), (SHOES, BLUE)])
STEP_2_COVERED = _png([(TOP, GREEN), (SHOES, BLUE)])  # the second product painted over the first


def test_an_earlier_product_still_in_the_final_image_is_verified():
    assert region_still_present(STEP_1, STEP_2, list(TOP))["status"] == VERIFIED


def test_an_earlier_product_covered_by_a_later_one_needs_review():
    result = region_still_present(STEP_1, STEP_2_COVERED, list(TOP))
    assert result["status"] == REVIEW_REQUIRED
    assert "covered or altered" in result["reason"]


def test_an_unmeasured_product_needs_review_rather_than_passing():
    assert region_still_present(STEP_1, STEP_2, None)["status"] == REVIEW_REQUIRED


async def test_the_whole_look_passes_only_when_every_product_is_confirmed():
    ok = await final_check(PERSON, STEP_2, [STEP_1, STEP_2], [list(TOP), list(SHOES)], [b"p1", b"p2"], ["Top", "Shoes"], with_vlm=False)
    assert ok["passed"] is True
    assert [p["status"] for p in ok["products"]] == [VERIFIED, VERIFIED]

    covered = await final_check(
        PERSON, STEP_2_COVERED, [STEP_1, STEP_2_COVERED], [list(TOP), list(SHOES)], [b"p1", b"p2"], ["Top", "Shoes"], with_vlm=False
    )
    assert covered["passed"] is False
    assert [p["status"] for p in covered["products"]] == [REVIEW_REQUIRED, VERIFIED]


async def test_a_product_the_vision_check_cannot_find_needs_review(monkeypatch):
    async def fake_vlm(original, final, images, names):  # noqa: ANN001
        return {
            "enabled": True,
            "same_person": True,
            "products": [
                {"index": 0, "present": True, "color_correct": True, "details_preserved": True, "placement_correct": True},
                {"index": 1, "present": False, "color_correct": False, "details_preserved": False, "placement_correct": False},
            ],
        }

    monkeypatch.setattr(fc, "vlm_final_check", fake_vlm)
    result = await final_check(PERSON, STEP_2, [STEP_1, STEP_2], [list(TOP), list(SHOES)], [b"p1", b"p2"], ["Top", "Shoes"], with_vlm=True)
    assert result["passed"] is False
    assert result["products"][1]["status"] == REVIEW_REQUIRED
    assert "present" in result["products"][1]["reasons"][0]


async def test_a_different_person_fails_the_look_even_with_every_product_present(monkeypatch):
    async def fake_vlm(original, final, images, names):  # noqa: ANN001
        row = {"present": True, "color_correct": True, "details_preserved": True, "placement_correct": True}
        return {"enabled": True, "same_person": False, "products": [{"index": 0, **row}, {"index": 1, **row}]}

    monkeypatch.setattr(fc, "vlm_final_check", fake_vlm)
    result = await final_check(PERSON, STEP_2, [STEP_1, STEP_2], [list(TOP), list(SHOES)], [b"p1", b"p2"], ["Top", "Shoes"], with_vlm=True)
    assert result["identity_ok"] is False and result["passed"] is False


async def test_an_unreadable_vision_answer_confirms_nothing(monkeypatch):
    async def fake_vlm(original, final, images, names):  # noqa: ANN001
        return {"enabled": True, "error": "timeout", "products": [], "same_person": None}

    monkeypatch.setattr(fc, "vlm_final_check", fake_vlm)
    result = await final_check(PERSON, STEP_2, [STEP_1, STEP_2], [list(TOP), list(SHOES)], [b"p1", b"p2"], ["Top", "Shoes"], with_vlm=True)
    assert result["passed"] is False
    assert all(p["status"] == REVIEW_REQUIRED for p in result["products"])
