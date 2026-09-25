"""OpenAI image-editing try-on: the whole outfit — shoes, bag, jewellery
included — goes to one /images/edits call with the person's photo and
every product photo, the way ChatGPT does it. No real network calls."""

from __future__ import annotations

import base64

import httpx
import pytest

from app.ai.providers.base import OutfitPiece, TryOnOutput
from app.core.config import get_settings
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
    """With the quality pipeline off: the screenshot's outfit (kameez, oxford
    shoes, duffle bag) goes to a whole-outfit provider in one call, and the
    outfit says all three are on the photo."""
    monkeypatch.setattr("app.workers.tasks.tryon_tasks.settings.TRYON_QUALITY_PIPELINE", False)
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


async def _outfit_with_shoes_and_bag(client, db):
    from tests.test_tryon import _upload_front_photo

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    outfit = Outfit(user_id=user_id)
    db.add(outfit)
    await db.flush()
    rows = [
        ("J. Shalwar Qameez Brown Color", OutfitSlot.DRESS, "https://img.example/kameez.jpg"),
        ("Men Leather Oxford Shoes", OutfitSlot.SHOES, "https://img.example/shoes.jpg"),
        ('18" Medium Duffle Bag Gym Sports Duffel', OutfitSlot.BAG, "https://img.example/bag.jpg"),
    ]
    for pos, (name, slot, img) in enumerate(rows):
        product = await seed_product(db, name=name, image_url=img)
        db.add(OutfitItem(outfit_id=outfit.id, product_id=product.id, slot=slot, position=pos))
    await db.commit()
    return photo_id, outfit.id


def _fashn_main_with_openai_for_full_looks(monkeypatch):
    """Production setup: FASHN is the main provider (clothing only) and an
    OpenAI key is set, so full looks go to OpenAI automatically."""
    from app.ai.providers.mock import MockTryOnProvider

    main = MockTryOnProvider()
    full = OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-1")
    for target in ("app.workers.tasks.tryon_tasks", "app.ai.providers.registry"):
        monkeypatch.setattr(f"{target}.get_tryon_provider", lambda: main)
        monkeypatch.setattr(f"{target}.get_full_look_provider", lambda: full)
    return main


async def test_a_look_with_shoes_and_a_bag_goes_to_openai_automatically(client, db, monkeypatch):
    """Real complaint: FASHN drew the kameez and left the shoes and bag off.
    Without anyone switching providers, a look FASHN can't fully draw is
    rendered by OpenAI — all three items."""
    from tests.test_tryon import _poll_until_terminal

    main = _fashn_main_with_openai_for_full_looks(monkeypatch)
    calls: list[list[OutfitPiece]] = []

    async def fake_generate_outfit(self, model_image_url, pieces):  # noqa: ARG001
        calls.append(pieces)
        return TryOnOutput(image_bytes=small_jpeg_bytes())

    async def main_must_not_run(self, payload):  # noqa: ARG001
        raise AssertionError("the clothing-only provider should not have been used")

    monkeypatch.setattr(OpenAIImageTryOnProvider, "generate_outfit", fake_generate_outfit)
    monkeypatch.setattr(type(main), "generate", main_must_not_run)

    photo_id, outfit_id = await _outfit_with_shoes_and_bag(client, db)
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "outfit_id": outfit_id})
    finished = await _poll_until_terminal(client, resp.json()["id"])

    assert finished["status"] == "completed", finished
    assert finished["provider"] == "openai"
    assert [p.slot for p in calls[0]] == ["dress", "shoes", "bag"]
    assert len(finished["outfit"]["rendered_item_ids"]) == 3


async def test_if_openai_fails_the_look_still_renders_with_the_main_provider(client, db, monkeypatch):
    """e.g. an OpenAI org that isn't verified for image models: the user
    still gets the clothing drawn by FASHN, and the labels say so."""
    from app.ai.providers.base import TryOnProviderError
    from tests.test_tryon import _poll_until_terminal

    main = _fashn_main_with_openai_for_full_looks(monkeypatch)

    async def openai_refuses(self, model_image_url, pieces):  # noqa: ARG001
        raise TryOnProviderError("OpenAI image edit failed (403): organization must be verified")

    main_calls: list[str] = []

    async def main_generate(self, payload):  # noqa: ARG001
        main_calls.append(payload.garment_image_url)
        return TryOnOutput(image_bytes=small_jpeg_bytes())

    monkeypatch.setattr(OpenAIImageTryOnProvider, "generate_outfit", openai_refuses)
    monkeypatch.setattr(type(main), "generate", main_generate)

    photo_id, outfit_id = await _outfit_with_shoes_and_bag(client, db)
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "outfit_id": outfit_id})
    finished = await _poll_until_terminal(client, resp.json()["id"])

    assert finished["status"] == "completed", finished
    assert finished["provider"] == "mock"
    assert main_calls == ["https://img.example/kameez.jpg"]
    kameez = next(i for i in finished["outfit"]["items"] if i["slot"] == "dress")
    assert finished["outfit"]["rendered_item_ids"] == [kameez["id"]]


def test_full_looks_stay_on_fashn_when_tryon_max_can_draw_them(monkeypatch):
    """OpenAI redraws the whole photo and can change the face; FASHN
    tryon-max only edits each item. When it's configured it draws shoes,
    bags and jewellery itself, so the look is never handed to OpenAI."""
    from app.ai.providers.fashn import FASHNTryOnProvider
    from app.ai.providers.registry import plan_outfit_render

    main = FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model="tryon-max")
    full = OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-1")
    monkeypatch.setattr("app.ai.providers.registry.get_tryon_provider", lambda: main)
    monkeypatch.setattr("app.ai.providers.registry.get_full_look_provider", lambda: full)

    provider, plan = plan_outfit_render(
        [
            (OutfitSlot.DRESS, "Men's Cotton Kurta Pajama Set"),
            (OutfitSlot.SHOES, "Men's Crossflex Dress Sneakers Wingtip"),
            (OutfitSlot.BAG, "Genuine Brown Leather duffle travel bag"),
        ]
    )
    assert provider is main
    assert [s for _, s in plan] == [OutfitSlot.DRESS, OutfitSlot.SHOES, OutfitSlot.BAG]



async def test_with_the_quality_pipeline_openai_renders_item_by_item_on_the_current_image(monkeypatch):
    """OpenAI redraws the whole photo too, so it goes through the same
    pipeline as FASHN: one product per call, on the pipeline's current image
    (handed over in memory), with the inspector's correction on a retry."""
    from app.workers.tasks.tryon_tasks import _pipeline_renderer
    from app.services.tryon_quality.pipeline import LookItem, RenderHint

    seen: list[tuple[str, list[OutfitPiece]]] = []

    async def fake_generate_outfit(self, model_image_url, pieces):  # noqa: ARG001
        seen.append((model_image_url, pieces))
        return TryOnOutput(image_bytes=b"render")

    monkeypatch.setattr(OpenAIImageTryOnProvider, "generate_outfit", fake_generate_outfit)
    render = _pipeline_renderer(OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-1"))
    item = LookItem("https://i.ebayimg.com/watch.jpg", OutfitSlot.WATCH, "Bulova Blue Dial Watch")

    hint = RenderHint(description="a steel watch, blue dial", fix="make the bracelet silver steel", seed=42)
    assert await render(b"current-image", item, hint) == b"render"
    url, pieces = seen[0]
    assert url.startswith("data:image/jpeg;base64,")
    assert [(p.name, p.slot, p.note, p.description) for p in pieces] == [
        ("Bulova Blue Dial Watch", "watch", "make the bracelet silver steel", "a steel watch, blue dial")
    ]


@pytest.mark.asyncio
async def test_the_correction_reaches_the_openai_prompt(monkeypatch):
    edits: list[httpx.Request] = []
    _patch_transport(monkeypatch, _image_handler(edits))
    provider = OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-1")
    await provider.generate_outfit(
        "data:image/jpeg;base64," + base64.b64encode(small_jpeg_bytes()).decode(),
        [OutfitPiece("https://i.ebayimg.com/w.jpg", "watch", "Bulova Watch", note="wrap it around the wrist")],
    )
    assert b"Correction from the previous attempt: wrap it around the wrist" in edits[0].content


@pytest.mark.asyncio
async def test_the_retry_renders_at_the_detailed_quality(monkeypatch):
    """Everyday renders use the fast setting; an item the inspector turned
    down is worth the slower one (an ivory dress came back pink at "low")."""
    from app.services.tryon_quality.pipeline import LookItem, RenderHint
    from app.workers.tasks.tryon_tasks import _pipeline_renderer

    qualities: list[str] = []

    async def fake_generate_outfit(self, model_image_url, pieces):  # noqa: ARG001
        qualities.append(self.quality)
        return TryOnOutput(image_bytes=b"render")

    monkeypatch.setattr(OpenAIImageTryOnProvider, "generate_outfit", fake_generate_outfit)
    provider = OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-2", quality="low")
    render = _pipeline_renderer(provider)
    item = LookItem("https://i.ebayimg.com/dress.jpg", OutfitSlot.DRESS, "Pakistani maxi dress")

    await render(b"img", item, RenderHint(description="ivory maxi dress"))
    await render(b"img", item, RenderHint(description="ivory maxi dress", fix="it is ivory, not pink", detail=True))
    assert qualities == ["low", get_settings().OPENAI_IMAGE_QUALITY_RETRY]
    assert provider.quality == "low"  # the original is left alone


def test_the_product_description_reaches_the_prompt():
    from app.ai.providers.openai_image import build_prompt

    prompt = build_prompt(
        [OutfitPiece("https://i.ebayimg.com/d.jpg", "dress", "Maxi dress", description="ivory, gold embroidery")]
    )
    assert "It is: ivory, gold embroidery" in prompt


@pytest.mark.asyncio
async def test_a_model_that_refuses_input_fidelity_is_only_asked_once(monkeypatch):
    """Live logs showed every render posting twice: a 400, then a retry
    that worked. The rejection arrives only after the whole multipart body
    — the photo and every product image — has gone up, so asking again on
    each render was uploading everything twice, all day."""
    from app.ai.providers import openai_image

    openai_image._NO_INPUT_FIDELITY.discard("gpt-image-2")
    posts: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if not request.url.path.endswith("/images/edits"):
            return httpx.Response(200, content=small_jpeg_bytes())  # the product photo
        sent = b"input_fidelity" in request.content
        posts.append(sent)
        if sent:
            return httpx.Response(400, json={"error": {"message": "Unknown parameter: 'input_fidelity'."}})
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"img").decode()}]})

    _patch_transport(monkeypatch, handler)
    provider = OpenAIImageTryOnProvider(api_key="sk-test", model="gpt-image-2")
    photo = "data:image/jpeg;base64," + base64.b64encode(small_jpeg_bytes()).decode()
    piece = [OutfitPiece("https://i.ebayimg.com/k.jpg", "dress", "Kameez")]

    await provider.generate_outfit(photo, piece)
    assert posts == [True, False]  # asked once, then told

    posts.clear()
    await provider.generate_outfit(photo, piece)
    await provider.generate_outfit(photo, piece)
    assert posts == [False, False]  # never asked again — no wasted uploads


def test_each_product_carries_its_own_preservation_rules():
    """Live: a tote with a crocodile-embossed base came back as a plain
    leather bag. "Reproduce each product faithfully" leaves the model to
    decide what faithfully means, and what a shopper would notice is
    different for a bag, a watch and a kameez."""
    from app.ai.providers.openai_image import build_prompt

    prompt = build_prompt([
        OutfitPiece("https://img/bag.jpg", "bag", "Leather Tote with Crocodile-Embossed Base"),
        OutfitPiece("https://img/watch.jpg", "watch", "Small Dial Leather Band Watch"),
    ])
    assert "handles" in prompt and "embossed" in prompt  # what makes that tote that tote
    assert "dial" in prompt and "strap colour" in prompt  # ...and that watch that watch


def test_a_multi_colour_listing_photo_is_told_to_pick_one():
    """That tote's only photo shows the same bag in brown, tan and cream."""
    from app.ai.providers.openai_image import build_prompt

    assert "several colours" in build_prompt([OutfitPiece("https://img/b.jpg", "bag", "Tote")])


def test_a_set_of_different_pieces_is_not_drawn_as_copies_of_one():
    """Live: a five-piece stack — a rope chain, a knot cuff, a beaded
    bangle, a flat cuff and a paperclip chain — came back as plain gold
    bangles, and on both wrists when the set is one stack."""
    from app.ai.providers.openai_image import build_prompt

    prompt = build_prompt([OutfitPiece("https://img/b.jpg", "accessory", "Stackable Bangle Set")])
    assert "one wrist, not both" in prompt
    assert "several copies of one plain piece" in prompt
