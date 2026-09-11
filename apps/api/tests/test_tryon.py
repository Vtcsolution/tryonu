"""The full try-on job lifecycle: credit debit on create, background
completion, and — the important safety property — automatic refund when
the provider fails. `MockTryOnProvider.generate` is patched to be instant
and network-free (no real FASHN/Unsplash calls in the test suite)."""

from __future__ import annotations

import asyncio

from app.ai.providers.base import TryOnOutput, TryOnProviderError
from app.ai.providers.mock import MockTryOnProvider
from app.models.enums import CreditReason
from app.services import credit_service
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
