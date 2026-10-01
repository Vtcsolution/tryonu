"""The zoned pipeline (render_zoned_look): zone/layer/deformation come
from a mocked zone_spec_for — never a title — large-region products
render first (max 3/call), every small-region product gets its own
zoomed pass (max 2-3/call), and the canvas stays pixel-locked to the
input photo's own resolution throughout. A batch NEVER mixes two
different zones — only products that share the exact same zone (two
earrings, several bangles) ever share one call; that's the whole point
of deriving zone from the photo rather than guessing placement. Offline —
downloads, zone classification, description, body-part lookup, the edit
call and judge() are all faked."""

from __future__ import annotations

import numpy as np
import pytest

from app.models.enums import OutfitSlot
from app.services.tryon_quality import zoned
from app.services.tryon_quality.compose import Region, decode, encode_jpeg
from app.services.tryon_quality.judge import Verdict
from app.services.tryon_quality.pipeline import LookItem
from app.services.tryon_quality.zone_spec import ZoneSpec
from app.services.tryon_quality.zoned import _zone_batches, render_zoned_look

GOOD = Verdict(9, 9, 8)

# Distinct, non-overlapping windows for every small-zone body-part lookup
# this pipeline can ask for.
_PART_REGION = {
    "the person's hands and wrists": Region(0.05, 0.55, 0.20, 0.68),
    "the person's neck, shoulders and upper chest": Region(0.40, 0.08, 0.60, 0.22),
    "where a bag would be carried: the person's hand, shoulder or side": Region(0.80, 0.55, 0.95, 0.75),
    "the person's feet and the shoes or footwear area": Region(0.30, 0.85, 0.70, 0.97),
    "where this item would naturally be worn or carried on the person": Region(0.82, 0.05, 0.95, 0.18),
}


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


# ------------------------------------------------------------ _zone_batches


def test_same_zone_items_share_a_batch_up_to_the_cap():
    specs = [ZoneSpec(zone="ears", layer=2, deformation="", large_region=False) for _ in range(5)]
    batches = _zone_batches(list(range(5)), specs, max_size=3)
    assert sorted(len(b) for b in batches) == [2, 3]
    assert sum(len(b) for b in batches) == 5


def test_different_zones_never_share_a_batch():
    specs = [
        ZoneSpec(zone="ears", layer=2, deformation="", large_region=False),
        ZoneSpec(zone="hand_wrist", layer=2, deformation="", large_region=False),
        ZoneSpec(zone="bag", layer=2, deformation="", large_region=False),
    ]
    batches = _zone_batches([0, 1, 2], specs, max_size=3)
    assert len(batches) == 3  # one per zone, even though the cap would allow all three together


# ------------------------------------------------------------- end to end


@pytest.mark.parametrize("n", [3, 5, 10, 15])
async def test_every_item_is_drawn_and_verified_for_any_product_count(fake_pipeline, monkeypatch, n):
    specs, verdicts = fake_pipeline
    items = []
    for i in range(n):
        item = _item(f"item{i}")
        items.append(item)
        # one real large-region garment, everything else a small-region
        # accessory in the same zone (several of the same thing — bangles,
        # say — which is exactly the case same-zone batching is for)
        if i == 0:
            specs[item.image_url] = ZoneSpec(zone="torso", layer=0, deformation="drapes over the torso", large_region=True)
        else:
            specs[item.image_url] = ZoneSpec(zone="other", layer=2, deformation="rigid", large_region=False)
        verdicts[item.image_url] = [GOOD]

    person = _photo()
    edit_calls: list[str] = []
    image_bytes, reports = await render_zoned_look(person, items, _editor(edit_calls), retries=1, budget_seconds=60)

    assert len(reports) == n
    assert all(r.verified for r in reports)
    assert set(edit_calls) == {item.name for item in items}  # every item actually went through a real edit call

    final = decode(image_bytes)
    base = decode(person)
    assert final.shape[:2] == base.shape[:2]  # pixel-lock: output resolution matches the input photo's


async def test_a_batch_of_same_zone_items_costs_one_call_not_one_per_item(fake_pipeline):
    """The actual cost-saving claim: up to 3 same-zone items (several
    bangles) share ONE edit_masked_batch() call, not 3 separate ones."""
    specs, verdicts = fake_pipeline
    items = [_item(f"bangle{i}") for i in range(3)]
    for item in items:
        specs[item.image_url] = ZoneSpec(zone="hand_wrist", layer=2, deformation="", large_region=False)
        verdicts[item.image_url] = [GOOD]

    batch_call_count = {"n": 0}

    async def counting_edit_batch(person_png, mask_png, pieces):  # noqa: ARG001
        batch_call_count["n"] += 1
        assert len(pieces) == 3  # all three shared the one call
        return _photo()

    await render_zoned_look(_photo(), items, counting_edit_batch, retries=1, budget_seconds=60)

    assert batch_call_count["n"] == 1


async def test_items_in_different_zones_never_share_a_call_even_when_few(fake_pipeline):
    """A ring (other) and a necklace (neck_chest) must never end up in the
    same edit call — the model guessing which window is whose is exactly
    the swap/misplacement risk this pipeline exists to avoid."""
    specs, verdicts = fake_pipeline
    ring, necklace = _item("ring"), _item("necklace")
    specs[ring.image_url] = ZoneSpec(zone="other", layer=2, deformation="", large_region=False)
    specs[necklace.image_url] = ZoneSpec(zone="neck_chest", layer=2, deformation="", large_region=False)
    verdicts[ring.image_url] = [GOOD]
    verdicts[necklace.image_url] = [GOOD]

    calls: list[list[str]] = []

    async def recording_edit_batch(person_png, mask_png, pieces):  # noqa: ARG001
        calls.append([p.item.name for p in pieces])
        return _photo()

    await render_zoned_look(_photo(), [ring, necklace], recording_edit_batch, retries=1, budget_seconds=60)

    assert len(calls) == 2
    assert all(len(c) == 1 for c in calls)


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


async def test_a_failed_item_retries_with_its_still_failing_batch_mate_only(fake_pipeline):
    specs, verdicts = fake_pipeline
    a, b = _item("ring1"), _item("ring2")
    # same zone -- they're allowed to share a batch
    specs[a.image_url] = ZoneSpec(zone="hand_wrist", layer=2, deformation="", large_region=False)
    specs[b.image_url] = ZoneSpec(zone="hand_wrist", layer=2, deformation="", large_region=False)
    bad = Verdict(3, 5, 6, ["wrong colour"], "make it gold")
    verdicts[a.image_url] = [bad, GOOD]  # fails once, then passes on retry
    verdicts[b.image_url] = [GOOD]

    edit_calls: list[str] = []
    _, reports = await render_zoned_look(_photo(), [a, b], _editor(edit_calls), retries=1, budget_seconds=60)

    a_report = next(r for r in reports if r.name == "ring1")
    b_report = next(r for r in reports if r.name == "ring2")
    assert a_report.verified
    assert a_report.attempts == 2  # one failure, one retry
    assert b_report.verified
    assert b_report.attempts == 1  # accepted on the shared batch's first round, never redrawn
