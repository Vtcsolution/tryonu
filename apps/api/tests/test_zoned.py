"""The zoned pipeline (render_zoned_look): zone/layer/deformation come
from a mocked zone_spec_for — never a title — large-region products
render first (max 3/call), every small-region product gets its own
zoomed pass (max 2-3/call), and the canvas stays pixel-locked to the
input photo's own resolution throughout. Offline — downloads, zone
classification, description, body-part lookup, the edit call and judge()
are all faked."""

from __future__ import annotations

import numpy as np
import pytest

from app.models.enums import OutfitSlot
from app.services.tryon_quality import zoned
from app.services.tryon_quality.compose import Region, decode, encode_jpeg
from app.services.tryon_quality.judge import Verdict
from app.services.tryon_quality.pipeline import LookItem
from app.services.tryon_quality.zone_spec import ZoneSpec
from app.services.tryon_quality.zoned import _batches, render_zoned_look

GOOD = Verdict(9, 9, 8)

# Distinct, non-overlapping windows for every small-zone body-part lookup
# this pipeline can ask for — lets a test build several small items that
# genuinely don't collide, to exercise real multi-item batching rather
# than every item landing in its own solo pass by geometric accident.
_PART_REGION = {
    "the person's hands and wrists": Region(0.05, 0.55, 0.20, 0.68),
    "the person's neck, shoulders and upper chest": Region(0.40, 0.08, 0.60, 0.22),
    "where a bag would be carried: the person's hand, shoulder or side": Region(0.80, 0.55, 0.95, 0.75),
    "the person's feet and the shoes or footwear area": Region(0.30, 0.85, 0.70, 0.97),
    "where this item would naturally be worn or carried on the person": Region(0.82, 0.05, 0.95, 0.18),
}
_PARTS = list(_PART_REGION.keys())


def _photo(h: int = 700, w: int = 450) -> bytes:
    return encode_jpeg(np.full((h, w, 3), 200, np.uint8), 95)


def _item(name: str) -> LookItem:
    return LookItem(image_url=f"https://img.example/{name}.jpg", slot=OutfitSlot.OTHER, name=name)


@pytest.fixture
def fake_pipeline(monkeypatch):
    specs: dict[str, ZoneSpec] = {}
    verdicts: dict[str, list[Verdict]] = {}

    async def download(url):  # noqa: ARG001
        return np.full((100, 100, 3), (10, 10, 200), np.uint8)

    async def spec_for(image, url):  # noqa: ARG001
        return specs[url]

    async def describe(image, url, name):  # noqa: ARG001
        return f"{name} (described)"

    async def locate(base, part):  # noqa: ARG001
        return _PART_REGION[part]

    async def judge(product, before, after, region, description, small_item, product_image_url):  # noqa: ARG001
        return verdicts[product_image_url].pop(0)

    monkeypatch.setattr(zoned, "_download", download)
    monkeypatch.setattr(zoned, "zone_spec_for", spec_for)
    monkeypatch.setattr(zoned, "describe_product", describe)
    monkeypatch.setattr(zoned, "find_body_part", locate)
    monkeypatch.setattr(zoned, "judge", judge)
    return specs, verdicts


def _editor(calls: list[str]):
    """A fake edit_masked_batch: one call may cover several items at
    once (a real batch), so every call records ALL of its pieces' names,
    not just one."""

    async def edit_batch(person_png, mask_png, pieces):  # noqa: ARG001
        calls.extend(p.item.name for p in pieces)
        return _photo()

    return edit_batch


# ---------------------------------------------------------------- _batches


def test_batches_never_exceed_the_cap_even_when_nothing_overlaps():
    regions = [Region(i * 0.1, 0.0, i * 0.1 + 0.05, 0.05) for i in range(7)]
    batches = _batches(list(range(7)), regions, max_size=3)
    assert all(len(b) <= 3 for b in batches)
    assert sum(len(b) for b in batches) == 7


def test_batches_split_overlapping_items_into_separate_groups():
    same = Region(0.1, 0.1, 0.5, 0.5)
    regions = [same, same, same]
    batches = _batches([0, 1, 2], regions, max_size=3)
    assert len(batches) == 3  # every item collides with every other — one per batch


# ------------------------------------------------------------- end to end


@pytest.mark.parametrize("n", [3, 5, 10, 15])
async def test_every_item_is_drawn_and_verified_for_any_product_count(fake_pipeline, monkeypatch, n):
    specs, verdicts = fake_pipeline
    items = []
    for i in range(n):
        item = _item(f"item{i}")
        items.append(item)
        # one real large-region garment, everything else a small-region
        # accessory — spread round-robin across distinct, non-overlapping
        # body-part slots so batching has real non-overlapping items to
        # group, not just solo passes by geometric coincidence
        if i == 0:
            specs[item.image_url] = ZoneSpec(zone="torso", layer=0, deformation="drapes over the torso", large_region=True)
        else:
            specs[item.image_url] = ZoneSpec(zone="other", layer=2, deformation="rigid", large_region=False)
        verdicts[item.image_url] = [GOOD]

    calls = {"n": 0}

    async def round_robin_locate(base, part):  # noqa: ARG001
        region = list(_PART_REGION.values())[calls["n"] % len(_PART_REGION)]
        calls["n"] += 1
        return region

    monkeypatch.setattr(zoned, "find_body_part", round_robin_locate)

    person = _photo()
    edit_calls: list[str] = []
    image_bytes, reports = await render_zoned_look(person, items, _editor(edit_calls), retries=1, budget_seconds=60)

    assert len(reports) == n
    assert all(r.verified for r in reports)
    assert set(edit_calls) == {item.name for item in items}  # every item actually went through a real edit call

    final = decode(image_bytes)
    base = decode(person)
    assert final.shape[:2] == base.shape[:2]  # pixel-lock: output resolution matches the input photo's


async def test_a_batch_of_non_overlapping_small_items_costs_one_call_not_one_per_item(fake_pipeline, monkeypatch):
    """The actual cost-saving claim: up to 3 non-overlapping small items
    share ONE edit_masked_batch() call, not 3 separate ones."""
    specs, verdicts = fake_pipeline
    items = [_item(f"acc{i}") for i in range(3)]
    for item in items:
        specs[item.image_url] = ZoneSpec(zone="other", layer=2, deformation="", large_region=False)
        verdicts[item.image_url] = [GOOD]

    parts = iter(_PARTS)

    async def distinct_locate(base, part):  # noqa: ARG001
        return _PART_REGION[next(parts)]

    monkeypatch.setattr(zoned, "find_body_part", distinct_locate)

    batch_call_count = {"n": 0}

    async def counting_edit_batch(person_png, mask_png, pieces):  # noqa: ARG001
        batch_call_count["n"] += 1
        assert len(pieces) == 3  # all three shared the one call
        return _photo()

    await render_zoned_look(_photo(), items, counting_edit_batch, retries=1, budget_seconds=60)

    assert batch_call_count["n"] == 1


async def test_large_region_items_render_before_small_region_ones(fake_pipeline):
    specs, verdicts = fake_pipeline
    small = _item("earrings")
    large = _item("dress")
    specs[small.image_url] = ZoneSpec(zone="ears", layer=2, deformation="", large_region=False)
    specs[large.image_url] = ZoneSpec(zone="torso", layer=0, deformation="drapes", large_region=True)
    verdicts[small.image_url] = [GOOD]
    verdicts[large.image_url] = [GOOD]

    edit_calls: list[str] = []
    await render_zoned_look(_photo(), [small, large], _editor(edit_calls), retries=1, budget_seconds=60)

    assert edit_calls.index("dress") < edit_calls.index("earrings")


async def test_a_failed_item_retries_on_its_own_without_affecting_a_sibling(fake_pipeline):
    specs, verdicts = fake_pipeline
    a, b = _item("ring"), _item("bracelet")
    specs[a.image_url] = ZoneSpec(zone="other", layer=2, deformation="", large_region=False)
    specs[b.image_url] = ZoneSpec(zone="hand_wrist", layer=2, deformation="", large_region=False)
    bad = Verdict(3, 5, 6, ["wrong colour"], "make it gold")
    verdicts[a.image_url] = [bad, GOOD]  # fails once, then passes on retry
    verdicts[b.image_url] = [GOOD]

    edit_calls: list[str] = []
    _, reports = await render_zoned_look(_photo(), [a, b], _editor(edit_calls), retries=1, budget_seconds=60)

    ring_report = next(r for r in reports if r.name == "ring")
    bracelet_report = next(r for r in reports if r.name == "bracelet")
    assert ring_report.verified
    assert ring_report.attempts == 2  # one failure, one retry
    assert bracelet_report.verified
    assert bracelet_report.attempts == 1  # untouched by the sibling's retry
