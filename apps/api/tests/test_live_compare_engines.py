"""The live-compare script's own mechanics — the call budget that must
stop BEFORE exceeding the cap, local debug file writes, and config
parsing. No real OpenAI call is ever made here; this script itself is
never run against the real API in this test suite, only offline."""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.models.enums import OutfitSlot
from app.scripts.live_compare_engines import CallBudget, CallBudgetExceeded, LocalDebug, _load_config


def test_budget_allows_calls_up_to_the_cap():
    budget = CallBudget(max_calls=3)
    budget.spend("a")
    budget.spend("b")
    budget.spend("c")
    assert budget.used == 3


def test_budget_refuses_before_exceeding_not_after():
    budget = CallBudget(max_calls=2)
    budget.spend("a")
    budget.spend("b")
    with pytest.raises(CallBudgetExceeded):
        budget.spend("c")
    assert budget.used == 2  # the refused call was never counted as spent


def test_local_debug_writes_bytes_and_arrays_to_disk(tmp_path):
    debug = LocalDebug(tmp_path, "old")
    debug.save("input", b"\x89PNGfakebytes")
    debug.save("provider_output", np.full((10, 10, 3), 200, np.uint8), label="item1")

    files = sorted((tmp_path / "old").glob("*"))
    assert len(files) == 2
    assert files[0].name == "01_input.png"
    assert files[1].name == "02_provider_output_item1.png"
    assert files[0].read_bytes() == b"\x89PNGfakebytes"


def test_load_config_parses_person_and_products(tmp_path):
    photo_path = tmp_path / "front.jpg"
    photo_path.write_bytes(b"\xff\xd8fake-jpeg")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "person_photo": str(photo_path),
                "products": [
                    {"name": "Pink Kameez", "image_url": "https://img.example/kameez.jpg", "slot": "dress"},
                    {"name": "Earrings", "image_url": "https://img.example/earrings.jpg", "slot": "accessory"},
                ],
            }
        )
    )

    person, items = _load_config(config_path)

    assert person == b"\xff\xd8fake-jpeg"
    assert [item.name for item in items] == ["Pink Kameez", "Earrings"]
    assert items[0].slot == OutfitSlot.DRESS
    assert items[1].slot == OutfitSlot.ACCESSORY
