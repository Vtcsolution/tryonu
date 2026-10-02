"""The live-compare script's own mechanics — the dollar budget that must
stop BEFORE exceeding the cap, local-file loading (never HTTP), local
debug writes, and the black-box detector. No real OpenAI/Gemini call is
ever made here; the script itself is never run against a real API in
this test suite, only offline."""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.models.enums import OutfitSlot
from app.scripts.live_compare_engines import (
    BudgetExceeded,
    CostBudget,
    LocalDebug,
    _detect_black_box,
    _load_manifest,
    _patch_local_downloads,
)


def test_budget_allows_spending_up_to_the_cap():
    budget = CostBudget(max_usd=0.10)
    budget.spend(0.04, "a")
    budget.spend(0.04, "b")
    assert budget.spent_usd == pytest.approx(0.08)


def test_budget_refuses_before_exceeding_not_after():
    budget = CostBudget(max_usd=0.10)
    budget.spend(0.06, "a")
    with pytest.raises(BudgetExceeded):
        budget.spend(0.06, "b")  # would bring total to 0.12, over the cap
    assert budget.spent_usd == pytest.approx(0.06)  # the refused spend was never counted


def test_local_debug_writes_bytes_and_arrays_to_disk(tmp_path):
    debug = LocalDebug(tmp_path, "zoned_openai")
    debug.save("input", b"\x89PNGfakebytes")
    debug.save("provider_output", np.full((10, 10, 3), 200, np.uint8), label="item1")

    files = sorted((tmp_path / "zoned_openai").glob("*"))
    assert len(files) == 2
    assert files[0].name == "01_input.png"
    assert files[1].name == "02_provider_output_item1.png"
    assert files[0].read_bytes() == b"\x89PNGfakebytes"


def test_load_manifest_reads_person_and_products_as_local_urls(tmp_path):
    photo_path = tmp_path / "person_front.jpg"
    photo_path.write_bytes(_jpeg_bytes())
    product_path = tmp_path / "1_kurti.jpg"
    product_path.write_bytes(_jpeg_bytes())
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "person_photo": "person_front.jpg",
                "products": [{"name": "White Kurti", "image_file": "1_kurti.jpg", "slot": "top"}],
            }
        )
    )

    person, items, local_images = _load_manifest(manifest_path)

    assert person == photo_path.read_bytes()
    assert items[0].name == "White Kurti"
    assert items[0].slot == OutfitSlot.TOP
    assert items[0].image_url == "local://1_kurti"
    assert "local://1_kurti" in local_images
    assert local_images["local://1_kurti"].shape[2] == 3  # decoded to a real BGR array


async def test_patch_local_downloads_resolves_registered_urls_only():
    img = np.full((20, 20, 3), 5, np.uint8)
    _patch_local_downloads({"local://x": img})

    from app.services.tryon_quality import masked as masked_module

    resolved = await masked_module._download("local://x")
    assert np.array_equal(resolved, img)

    with pytest.raises(ValueError):
        await masked_module._download("local://not-registered")


def test_detect_black_box_finds_a_large_flat_dark_rectangle():
    image = np.full((400, 300, 3), 200, np.uint8)
    image[50:150, 50:200] = 2  # a large, perfectly flat dark rectangle — the exact bug symptom
    found = _detect_black_box(image)
    assert found is not None
    assert found["share"] > 0.01


def test_detect_black_box_ignores_real_dark_photo_content():
    rng = np.random.default_rng(1)
    image = np.full((400, 300, 3), 200, np.uint8)
    # dark but textured — real hair/shadow has meaningful local contrast,
    # not a flat paste failure (a narrower random band still averages to
    # a near-flat grayscale image once the 3 channels are combined)
    image[50:150, 50:200] = rng.integers(0, 90, (100, 150, 3), dtype=np.uint8)
    assert _detect_black_box(image) is None


def _jpeg_bytes() -> bytes:
    import cv2

    ok, buf = cv2.imencode(".jpg", np.full((100, 100, 3), 180, np.uint8))
    assert ok
    return buf.tobytes()
