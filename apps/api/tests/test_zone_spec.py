"""zone_spec_for(): classifies a product's zone/layer/deformation from its
own photo alone — the prompt never mentions a name or title, and these
tests never pass one in. ask_json is mocked (no network); caching uses
the real local-disk storage backend, the same way test_cutout.py does."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.tryon_quality import zone_spec as zone_spec_module
from app.services.tryon_quality.vision import VisionError
from app.services.tryon_quality.zone_spec import ZoneSpec, zone_spec_for


def _product_image() -> np.ndarray:
    return np.full((200, 200, 3), (10, 10, 200), np.uint8)


async def test_classifies_from_the_mocked_vision_answer(monkeypatch):
    seen_content = []

    async def fake_ask_json(instructions, content, **kw):  # noqa: ARG001
        seen_content.append(content)
        return {"zone": "hand_wrist", "layer": 4, "deformation": "wraps the wrist", "large_region": False}

    monkeypatch.setattr(zone_spec_module, "ask_json", fake_ask_json)

    spec = await zone_spec_for(_product_image(), "https://img.example/zone-spec-watch.jpg")

    assert spec == ZoneSpec(zone="hand_wrist", layer=4, deformation="wraps the wrist", large_region=False)
    # the call sends only the image — no listing title/name text part at all,
    # unlike describe_product()'s "Listing title: ..." text part
    assert all(part.get("type") != "text" for part in seen_content[0])


async def test_is_cached_on_the_second_call(monkeypatch):
    calls = []

    async def fake_ask_json(instructions, content, **kw):  # noqa: ARG001
        calls.append(1)
        return {"zone": "ears", "layer": 3, "deformation": "", "large_region": False}

    monkeypatch.setattr(zone_spec_module, "ask_json", fake_ask_json)

    url = "https://img.example/zone-spec-cache-test.jpg"
    first = await zone_spec_for(_product_image(), url)
    assert len(calls) == 1
    second = await zone_spec_for(_product_image(), url)
    assert len(calls) == 1
    assert first == second


async def test_falls_back_to_a_conservative_small_item_default_when_vision_is_unavailable(monkeypatch):
    async def fake_ask_json(instructions, content, **kw):  # noqa: ARG001
        raise VisionError("no OpenAI API key")

    monkeypatch.setattr(zone_spec_module, "ask_json", fake_ask_json)

    spec = await zone_spec_for(_product_image(), "https://img.example/zone-spec-unavailable.jpg")

    assert spec.large_region is False  # never silently treated as a large-region garment


async def test_an_unrecognised_zone_in_the_answer_falls_back_to_other(monkeypatch):
    async def fake_ask_json(instructions, content, **kw):  # noqa: ARG001
        return {"zone": "a completely made up zone", "layer": 2, "deformation": "", "large_region": False}

    monkeypatch.setattr(zone_spec_module, "ask_json", fake_ask_json)

    spec = await zone_spec_for(_product_image(), "https://img.example/zone-spec-bad-zone.jpg")

    assert spec.zone == "other"
