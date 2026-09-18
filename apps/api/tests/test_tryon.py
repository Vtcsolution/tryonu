"""The full try-on job lifecycle: credit debit on create, background
completion, and — the important safety property — automatic refund when
the provider fails. `MockTryOnProvider.generate` is patched to be instant
and network-free (no real FASHN/Unsplash calls in the test suite)."""

from __future__ import annotations

import asyncio

from app.ai.providers.base import TryOnOutput, TryOnProviderError
from app.ai.providers.mock import MockTryOnProvider
from app.models.enums import CreditReason, OutfitSlot
from app.models.outfit import Outfit, OutfitItem
from app.services import credit_service
from app.workers.tasks.tryon_tasks import _renderable_slots
from tests.conftest import credit_balance, register_and_login, seed_product, small_jpeg_bytes

TERMINAL = {"completed", "failed", "cancelled"}


async def _poll_until_terminal(client, job_id: str, *, attempts: int = 40, delay: float = 0.05) -> dict:
    for _ in range(attempts):
        resp = await client.get(f"/api/v1/tryon/{job_id}")
        job = resp.json()
        if job["status"] in TERMINAL:
            return job
        await asyncio.sleep(delay)
    raise AssertionError(f"job {job_id} never reached a terminal state: {job}")


async def _upload_front_photo(client) -> str:
    files = {"file": ("front.jpg", small_jpeg_bytes(), "image/jpeg")}
    resp = await client.post("/api/v1/photos", files=files, data={"kind": "front"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _upload_back_photo(client) -> str:
    files = {"file": ("back.jpg", small_jpeg_bytes(), "image/jpeg")}
    resp = await client.post("/api/v1/photos", files=files, data={"kind": "back"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_tryon_success_debits_credits_and_completes(client, db, monkeypatch):
    async def fake_generate(self, payload):  # noqa: ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db, name="Try-On Target")
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]

    assert await credit_balance(db, user_id) == 100

    resp = await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id}
    )
    assert resp.status_code == 201, resp.text
    job = resp.json()
    assert job["status"] == "queued"
    assert job["credit_cost"] == 5

    # credits are debited synchronously, before the job even starts running
    assert await credit_balance(db, user_id) == 95

    finished = await _poll_until_terminal(client, job["id"])
    assert finished["status"] == "completed"
    assert finished["result"]["image_url"]
    # no refund on success
    assert await credit_balance(db, user_id) == 95


async def test_tryon_failure_refunds_credits(client, db, monkeypatch):
    async def fake_generate(self, payload):  # noqa: ARG001
        raise TryOnProviderError("provider exploded", retryable=False)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db, name="Doomed Product")
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]

    resp = await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id}
    )
    job = resp.json()
    assert await credit_balance(db, user_id) == 95  # debited immediately

    finished = await _poll_until_terminal(client, job["id"])
    assert finished["status"] == "failed"
    assert finished["error_message"]

    # the whole point: a failed job must not leave the user out of pocket
    assert await credit_balance(db, user_id) == 100


async def test_tryon_failure_with_a_long_provider_error_still_completes_cleanly(client, db, monkeypatch):
    """Real bug found via live Postgres verification: AIUsage.error_message
    is VARCHAR(512), but the code wrote str(exc) unbounded — invisible on
    SQLite (no length enforcement) but a hard DB error on real Postgres,
    which left the job stuck in "processing" forever (the failing commit
    never persisted the FAILED status or the refund). A real FASHN
    ImageLoadError's message (with a nested urllib3 traceback) is exactly
    the shape that triggered this."""

    async def fake_generate(self, payload):  # noqa: ARG001
        raise TryOnProviderError("x" * 1000, retryable=False)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db, name="Long Error Product")
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    job = resp.json()
    assert await credit_balance(db, user_id) == 95  # debited immediately

    finished = await _poll_until_terminal(client, job["id"])
    assert finished["status"] == "failed"
    assert await credit_balance(db, user_id) == 100  # refunded, not stuck

    # SQLite (this test DB) doesn't enforce VARCHAR length like Postgres
    # does, so also directly assert the invariant the fix relies on —
    # otherwise this test can't actually catch a regression.
    from sqlalchemy import select as sa_select

    from app.models.ai_usage import AIUsage

    usage = (
        await db.execute(sa_select(AIUsage).where(AIUsage.reference_id == job["id"]))
    ).scalar_one()
    assert usage.error_message is not None
    assert len(usage.error_message) <= 512


async def test_tryon_requires_exactly_one_of_product_or_outfit(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": "whatever"})
    assert resp.status_code == 400


async def test_tryon_rejects_photo_belonging_to_another_user(client, db):
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db)

    # a second, different user tries to use the first user's photo id
    await register_and_login(client)
    resp = await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id}
    )
    assert resp.status_code == 404


async def _seed_outfit(db, user_id: str, slots: list[OutfitSlot]) -> Outfit:
    outfit = Outfit(user_id=user_id)
    db.add(outfit)
    await db.flush()
    for pos, slot in enumerate(slots):
        product = await seed_product(db, name=f"{slot.value}-item-{pos}")
        db.add(OutfitItem(outfit_id=outfit.id, product_id=product.id, slot=slot, position=pos))
    await db.commit()
    await db.refresh(outfit)
    return outfit


async def test_outfit_tryon_only_composites_renderable_slots(client, db, monkeypatch):
    """A shirt (TOP) gets layered via FASHN; shoes (SHOES) don't — FASHN
    composites clothing onto a body, not footwear. Real bug fixed this
    session: the worker used to try to layer every outfit item regardless
    of slot."""
    calls: list[str] = []

    async def fake_generate(self, payload):  # noqa: ARG001
        calls.append(payload.garment_image_url)
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    outfit = await _seed_outfit(db, user_id, [OutfitSlot.TOP, OutfitSlot.SHOES])

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "outfit_id": outfit.id})
    assert resp.status_code == 201, resp.text
    job = resp.json()
    assert job["credit_cost"] == 8  # outfit cost, not the single-item cost

    finished = await _poll_until_terminal(client, job["id"])
    assert finished["status"] == "completed"
    # exactly one FASHN call — the shoes were matched but never rendered
    assert len(calls) == 1
    assert finished["outfit"]["items"][0]["slot"] == "top"
    assert finished["outfit"]["items"][1]["slot"] == "shoes"


async def test_outfit_tryon_draws_the_full_outfit_first_then_layers_over_it(client, db, monkeypatch):
    """Real bug: a kurta pajama saved as "other" was never drawn, so the
    photo kept its jeans with only the waistcoat on top. It's re-classified
    at render time and drawn before the waistcoat; the bangle stays a
    matched product."""
    calls: list[str] = []

    async def fake_generate(self, payload):  # noqa: ARG001
        calls.append(payload.garment_image_url)
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]

    outfit = Outfit(user_id=user_id)
    db.add(outfit)
    await db.flush()
    rows = [
        ("Men's Paisley Formal Tuxedo Vest Tie & Hankie set", OutfitSlot.OUTERWEAR, "https://img.example/vest.jpg"),
        ("White Indian Cotton Kurta Pajama Men's Shalwar kameez", OutfitSlot.OTHER, "https://img.example/kurta.jpg"),
        ("Kundan Bangles Set", OutfitSlot.OTHER, "https://img.example/bangles.jpg"),
    ]
    for pos, (name, slot, img) in enumerate(rows):
        product = await seed_product(db, name=name, image_url=img)
        db.add(OutfitItem(outfit_id=outfit.id, product_id=product.id, slot=slot, position=pos))
    await db.commit()

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "outfit_id": outfit.id})
    assert resp.status_code == 201, resp.text
    finished = await _poll_until_terminal(client, resp.json()["id"])
    assert finished["status"] == "completed"
    assert calls == ["https://img.example/kurta.jpg", "https://img.example/vest.jpg"]


def test_renderable_slots_only_adds_shoes_for_tryon_max():
    """tryon-v1.6's "category" field only accepts tops/bottoms/one-pieces —
    confirmed live against FASHN's API that tryon-max has no such
    restriction, so shoes render only under that specific model. A
    deployment still on v1.6 must never get footwear sent to it."""
    assert OutfitSlot.SHOES in _renderable_slots("tryon-max")
    assert OutfitSlot.SHOES not in _renderable_slots("tryon-v1.6")
    assert OutfitSlot.SHOES not in _renderable_slots("mock-v1")
    assert OutfitSlot.ACCESSORY not in _renderable_slots("tryon-max")


async def test_outfit_tryon_with_only_non_renderable_items_fails_clearly(client, db):
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]
    outfit = await _seed_outfit(db, user_id, [OutfitSlot.SHOES, OutfitSlot.ACCESSORY])

    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "outfit_id": outfit.id})
    job = resp.json()

    finished = await _poll_until_terminal(client, job["id"])
    assert finished["status"] == "failed"
    assert "footwear" in finished["error_message"].lower() or "accessories" in finished["error_message"].lower()
    # refunded, same guarantee as any other failed job
    assert await credit_balance(db, user_id) == 100


async def test_tryon_insufficient_credits_returns_402(client, db):
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]

    # spend everything down to 3 (below the 5-credit try-on cost)
    await credit_service.debit(
        db, user_id=user_id, amount=97, reason=CreditReason.ADMIN_ADJUSTMENT,
        reference_type="test", reference_id="drain",
    )
    await db.commit()

    resp = await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id}
    )
    assert resp.status_code == 402


async def test_multi_tryon_creates_one_job_per_photo_and_shows_which_angle(client, db, monkeypatch):
    """"Show me the front and the back" — one job per uploaded angle, same
    product, each result tagged with which photo it came from."""
    async def fake_generate(self, payload):  # noqa: ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)

    await register_and_login(client)
    front_id = await _upload_front_photo(client)
    back_id = await _upload_back_photo(client)
    product = await seed_product(db, name="Multi-Angle Product")
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]

    resp = await client.post(
        "/api/v1/tryon/multi", json={"user_photo_ids": [front_id, back_id], "product_id": product.id}
    )
    assert resp.status_code == 201, resp.text
    jobs = resp.json()
    assert len(jobs) == 2
    assert {j["user_photo"]["kind"] for j in jobs} == {"front", "back"}
    assert all(j["credit_cost"] == 5 for j in jobs)
    # charged for both up front — one debit per job, same as two single calls
    assert await credit_balance(db, user_id) == 90

    for job in jobs:
        finished = await _poll_until_terminal(client, job["id"])
        assert finished["status"] == "completed"


async def test_multi_tryon_requires_at_least_two_photos(client, db):
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db)

    resp = await client.post(
        "/api/v1/tryon/multi", json={"user_photo_ids": [photo_id], "product_id": product.id}
    )
    assert resp.status_code == 400


async def test_multi_tryon_rejects_duplicate_photo_ids(client, db):
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db)

    resp = await client.post(
        "/api/v1/tryon/multi", json={"user_photo_ids": [photo_id, photo_id], "product_id": product.id}
    )
    assert resp.status_code == 400


async def test_multi_tryon_checks_total_cost_upfront_not_partway(client, db):
    """Real design requirement: with just enough credits for ONE job but
    not two, the whole batch must be rejected before any job (and its
    debit) is created — never leaving the user with only one of the two
    angles they asked for."""
    await register_and_login(client)
    front_id = await _upload_front_photo(client)
    back_id = await _upload_back_photo(client)
    product = await seed_product(db)
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]

    # leave exactly 5 credits — enough for one job (cost 5), not two (cost 10)
    await credit_service.debit(
        db, user_id=user_id, amount=95, reason=CreditReason.ADMIN_ADJUSTMENT,
        reference_type="test", reference_id="drain-multi",
    )
    await db.commit()

    resp = await client.post(
        "/api/v1/tryon/multi", json={"user_photo_ids": [front_id, back_id], "product_id": product.id}
    )
    assert resp.status_code == 402
    # nothing was charged — not even a partial debit for the one job that
    # would have fit
    assert await credit_balance(db, user_id) == 5


async def _create_wardrobe_item_with_photo(client, *, name: str = "My Denim Jacket") -> str:
    item = (await client.post("/api/v1/wardrobe", json={"name": name})).json()
    files = {"file": ("item.jpg", small_jpeg_bytes(), "image/jpeg")}
    resp = await client.post(f"/api/v1/wardrobe/{item['id']}/photo", files=files)
    assert resp.status_code == 200, resp.text
    return item["id"]


async def test_wardrobe_item_tryon_composites_the_users_own_upload(client, db, monkeypatch):
    """"Upload your own item" — never a shoppable Product, just the user's
    own photo composited onto their fitting photo."""
    async def fake_generate(self, payload):  # noqa: ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    item_id = await _create_wardrobe_item_with_photo(client, name="Vintage Denim Jacket")
    user_id = (await client.get("/api/v1/auth/me")).json()["id"]

    resp = await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "wardrobe_item_id": item_id}
    )
    assert resp.status_code == 201, resp.text
    job = resp.json()
    assert job["credit_cost"] == 5
    assert job["wardrobe_item"]["name"] == "Vintage Denim Jacket"
    assert job["product"] is None
    assert job["outfit"] is None

    finished = await _poll_until_terminal(client, job["id"])
    assert finished["status"] == "completed"
    assert finished["result"]["image_url"]


async def test_wardrobe_item_tryon_requires_a_photo_first(client, db):
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    item = (await client.post("/api/v1/wardrobe", json={"name": "No Photo Yet"})).json()

    resp = await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "wardrobe_item_id": item["id"]}
    )
    assert resp.status_code == 400


async def test_wardrobe_item_tryon_rejects_someone_elses_item(client, db):
    await register_and_login(client)
    item_id = await _create_wardrobe_item_with_photo(client)

    # a second, different user shouldn't be able to try on someone else's upload
    await client.post("/api/v1/auth/logout")
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)

    resp = await client.post(
        "/api/v1/tryon", json={"user_photo_id": photo_id, "wardrobe_item_id": item_id}
    )
    assert resp.status_code == 404


async def test_tryon_rejects_more_than_one_target(client, db):
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db)
    item_id = await _create_wardrobe_item_with_photo(client)

    resp = await client.post(
        "/api/v1/tryon",
        json={"user_photo_id": photo_id, "product_id": product.id, "wardrobe_item_id": item_id},
    )
    assert resp.status_code == 400


async def test_fitting_profile_is_ready_with_just_a_front_photo(client):
    await register_and_login(client)
    assert (await client.get("/api/v1/photos/status")).json()["is_ready"] is False

    await _upload_front_photo(client)
    status = (await client.get("/api/v1/photos/status")).json()
    assert status["is_ready"] is True
    assert status["has_back"] is False
