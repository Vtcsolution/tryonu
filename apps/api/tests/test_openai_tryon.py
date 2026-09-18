"""OpenAI image-editing try-on: the whole outfit — shoes, bag, jewellery
included — goes to one /images/edits call with the person's photo and
every product photo, the way ChatGPT does it. No real network calls."""

from __future__ import annotations

import base64

import httpx
import pytest

from app.ai.providers.base import OutfitPiece, TryOnOutput
from app.ai.providers.openai_image import OpenAIImageTryOnProvider
from app.models.enums import OutfitSlot
from app.models.outfit import Outfit, OutfitItem
from tests.conftest import register_and_login, seed_product, small_jpeg_bytes

RESULT = b"\xff\xd8rendered-look"


def _patch_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _image_handler(edits: list[httpx.Request], *, reject_fidelity: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/edits"):
            edits.append(request)
            if reject_fidelity and b'name="input_fidelity"' in request.content:
                return httpx.Response(400, json={"error": {"message": "Unknown parameter: 'input_fidelity'."}})
            return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(RESULT).decode()}]})
        return httpx.Response(200, content=small_jpeg_bytes(), headers={"content-type": "image/jpeg"})

    return handler


@pytest.mark.asyncio
async def test_sends_the_person_and_every_product_in_one_edit(monkeypatch):
    edits: list[httpx.Request] = []
    _patch_transport(monkeypatch, _image_handler(edits))
    provider = OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-1")

    out = await provider.generate_outfit(
        "https://api.example/media/me.jpg",
        [
            OutfitPiece("https://i.ebayimg.com/kameez.jpg", "dress", "Olive Cotton Shalwar Kameez"),
            OutfitPiece("https://i.ebayimg.com/oxford.jpg", "shoes", "Men Leather Oxford Shoes"),
            OutfitPiece("https://i.ebayimg.com/duffle.jpg", "bag", "DALIX Duffle Bag"),
        ],
    )

    assert out.image_bytes == RESULT
    assert len(edits) == 1
    body = edits[0].content
    assert edits[0].headers["authorization"] == "Bearer sk-test"
    assert body.count(b'name="image[]"') == 4  # the person + 3 products
    assert b"gpt-image-1" in body
    assert b"input_fidelity" in body
    assert b"Image 2: Olive Cotton Shalwar Kameez" in body
    assert b"Image 3: Men Leather Oxford Shoes" in body and b"on the feet" in body
    assert b"Image 4: DALIX Duffle Bag" in body and b"carried naturally" in body
    assert b"Keep the person exactly the same" in body


@pytest.mark.asyncio
async def test_retries_without_input_fidelity_for_models_that_reject_it(monkeypatch):
    edits: list[httpx.Request] = []
    _patch_transport(monkeypatch, _image_handler(edits, reject_fidelity=True))
    provider = OpenAIImageTryOnProvider(api_key="sk-test", model="some-image-model")

    out = await provider.generate_outfit(
        "https://api.example/media/me.jpg", [OutfitPiece("https://i.ebayimg.com/k.jpg", "dress", "Kameez")]
    )
    assert out.image_bytes == RESULT
    assert len(edits) == 2
    assert b"input_fidelity" not in edits[1].content


async def test_whole_outfit_provider_gets_every_item_in_one_call(client, db, monkeypatch):
    """The screenshot's outfit: kameez, oxford shoes, duffle bag. FASHN v1.6
    could only draw the kameez; a whole-outfit provider gets all three, in
    one call, and the outfit says all three are on the photo."""
    calls: list[list[OutfitPiece]] = []

    async def fake_generate_outfit(self, model_image_url, pieces):  # noqa: ARG001
        calls.append(pieces)
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id=None, latency_ms=1)

    monkeypatch.setattr(OpenAIImageTryOnProvider, "generate_outfit", fake_generate_outfit)
    monkeypatch.setattr(
        "app.workers.tasks.tryon_tasks.get_tryon_provider",
        lambda: OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-1"),
    )
    monkeypatch.setattr(
        "app.ai.providers.registry.get_tryon_provider",
        lambda: OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-1"),
    )

    from tests.test_tryon import _poll_until_terminal, _upload_front_photo

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    outfit = Outfit(user_id=user_id)
    db.add(outfit)
    await db.flush()
    rows = [
        ("DALIX Brand New Duffle Bag Sports Gym Bag", OutfitSlot.BAG, "https://img.example/bag.jpg"),
        ("Men Leather Oxford Shoes Formal Lace Up", OutfitSlot.SHOES, "https://img.example/shoes.jpg"),
        ("Pakistani Ready To Wear Men's Cotton Kameez Shalwar", OutfitSlot.OTHER, "https://img.example/kameez.jpg"),
    ]
    for pos, (name, slot, img) in enumerate(rows):
        product = await seed_product(db, name=name, image_url=img)
        db.add(OutfitItem(outfit_id=outfit.id, product_id=product.id, slot=slot, position=pos))
    await db.commit()

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "outfit_id": outfit.id})
    assert resp.status_code == 201, resp.text
    finished = await _poll_until_terminal(client, resp.json()["id"])
    assert finished["status"] == "completed", finished

    assert len(calls) == 1
    assert [(p.slot, p.image_url.rsplit("/", 1)[-1]) for p in calls[0]] == [
        ("dress", "kameez.jpg"),
        ("shoes", "shoes.jpg"),
        ("bag", "bag.jpg"),
    ]
    assert sorted(finished["outfit"]["rendered_item_ids"]) == sorted(i["id"] for i in finished["outfit"]["items"])
