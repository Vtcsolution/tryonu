"""The live-user-simulation script's own mechanics: creating/reusing the
dedicated test user, storing a real photo through the real validation
path, and building LookItems from stylist-picked products. No real
OpenAI/Gemini/stylist call is made here — those are exercised for real
only when the script itself is run, never in this suite."""

from __future__ import annotations

import numpy as np
import pytest

from app.models.enums import OutfitSlot
from app.scripts.live_user_simulation import (
    BillingHalted,
    BudgetExceeded,
    CostBudget,
    _detect_black_box,
    _get_or_create_test_user,
    _look_items,
    _store_front_photo,
)


def test_budget_refuses_before_exceeding_not_after():
    budget = CostBudget(max_usd=0.10)
    budget.preflight(0.06, "a")
    budget.charge(0.06, "a")
    with pytest.raises(BudgetExceeded):
        budget.preflight(0.06, "b")
    assert budget.spent_usd == pytest.approx(0.06)


def test_a_failed_call_is_never_charged():
    budget = CostBudget(max_usd=0.10)
    budget.preflight(0.06, "a")  # the attempt; charge() is never called since the call fails
    assert budget.spent_usd == 0.0


def test_halt_blocks_every_subsequent_preflight():
    budget = CostBudget(max_usd=10.0)
    budget.halt("no credits remaining")
    with pytest.raises(BillingHalted):
        budget.preflight(0.01, "next item")


def test_detect_black_box_finds_a_large_flat_dark_rectangle():
    image = np.full((400, 300, 3), 200, np.uint8)
    image[50:150, 50:200] = 2
    assert _detect_black_box(image) is not None


async def test_get_or_create_test_user_is_idempotent(db):
    first = await _get_or_create_test_user(db)
    second = await _get_or_create_test_user(db)
    assert first.id == second.id
    assert first.email == "live-sim@tryonu.test"


async def test_store_front_photo_persists_a_real_row(db, tmp_path):
    import cv2

    photo_path = tmp_path / "front.jpg"
    ok, buf = cv2.imencode(".jpg", np.full((600, 400, 3), 180, np.uint8))
    photo_path.write_bytes(buf.tobytes())

    user = await _get_or_create_test_user(db)
    photo = await _store_front_photo(db, user, photo_path)

    assert photo.user_id == user.id
    assert photo.kind.value == "front"
    assert photo.width == 400 and photo.height == 600


def test_look_items_skips_products_with_no_image():
    from app.models.product import Product

    class _FakeProduct:
        def __init__(self, name, image_url):
            self.name = name
            self._image_url = image_url

        @property
        def primary_image_url(self):
            return self._image_url

    with_image = _FakeProduct("White Chikankari Kurti", "https://img.example/kurti.jpg")
    without_image = _FakeProduct("Mystery Item", None)

    items = _look_items([with_image, without_image])

    assert len(items) == 1
    assert items[0].name == "White Chikankari Kurti"
    assert items[0].slot == OutfitSlot.TOP
