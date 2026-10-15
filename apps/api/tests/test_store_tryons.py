"""A store pays for shoppers' try-ons of its products, with the shopper's consent."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.providers.base import TryOnOutput, TryOnProviderError
from app.ai.providers.mock import MockTryOnProvider
from app.api.v1.endpoints.stores import _tryons_out
from app.models.store import Store, StorePlan, StoreTryOn
from tests.conftest import credit_balance, register_and_login, small_jpeg_bytes
from tests.test_stores import _clean, _live_store_with_product  # noqa: F401 - _clean is an autouse fixture
from tests.test_tryon import _poll_until_terminal, _upload_front_photo


async def _store_with_credits(client, db, credits):  # noqa: ANN001, ANN202
    basic = await db.scalar(select(StorePlan).where(StorePlan.code == "basic"))
    basic.tryon_credits = credits
    await db.commit()
    store, product = await _live_store_with_product(client, db)
    basic.tryon_credits = 0
    await db.commit()
    return store, product


async def _shopper_picks(client, store, product):  # noqa: ANN001, ANN202
    data = await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    picked = (await client.post(f"/api/v1/stores/public/{store['slug']}/products/{product['id']}/select")).json()
    return data["user"]["id"], photo_id, picked["product_id"]


def _instant(monkeypatch, *, fail=False):  # noqa: ANN001, ANN202
    async def fake_generate(self, payload):  # noqa: ANN001, ANN202, ARG001
        if fail:
            raise TryOnProviderError("broken", retryable=False)
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)


async def test_the_store_pays_and_sees_the_picture_when_the_shopper_shares(client, db, monkeypatch):  # noqa: ANN001
    _instant(monkeypatch)
    store, product = await _store_with_credits(client, db, 2)
    assert (await db.get(Store, store["id"])).tryon_credits == 2
    user_id, photo_id, product_id = await _shopper_picks(client, store, product)

    sponsor = (await client.get("/api/v1/tryon/sponsor", params={"product_id": product_id})).json()
    assert sponsor == {"store_id": store["id"], "store_name": "Lahore Couture"}

    before = await credit_balance(db, user_id)
    job = (await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product_id, "use_store_credit": True})).json()
    assert job["credit_cost"] == 0 and await credit_balance(db, user_id) == before  # free for the shopper
    assert (await _poll_until_terminal(client, job["id"]))["status"] == "completed"

    row = await db.get(Store, store["id"])
    await db.refresh(row)
    assert row.tryon_credits == 1
    out = await _tryons_out(db, row)
    assert out.used_by_store == 1 and out.credits_left == 1 and len(out.pictures) == 1
    assert out.pictures[0].product_name == "Pink Bridal Lehenga" and out.pictures[0].image_url


async def test_a_private_try_on_is_paid_by_the_shopper_and_only_counted(client, db, monkeypatch):  # noqa: ANN001
    _instant(monkeypatch)
    store, product = await _store_with_credits(client, db, 2)
    user_id, photo_id, product_id = await _shopper_picks(client, store, product)
    before = await credit_balance(db, user_id)

    job = (await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product_id})).json()
    assert await credit_balance(db, user_id) == before - job["credit_cost"] and job["credit_cost"] > 0
    await _poll_until_terminal(client, job["id"])

    row = await db.get(Store, store["id"])
    await db.refresh(row)
    out = await _tryons_out(db, row)
    assert row.tryon_credits == 2  # the store paid nothing
    assert out.tryons_total == 1 and out.private_tryons == 1 and out.pictures == []


async def test_no_credits_left_means_no_free_try_on_and_nothing_charged(client, db, monkeypatch):  # noqa: ANN001
    _instant(monkeypatch)
    store, product = await _store_with_credits(client, db, 0)
    user_id, photo_id, product_id = await _shopper_picks(client, store, product)
    before = await credit_balance(db, user_id)

    assert (await client.get("/api/v1/tryon/sponsor", params={"product_id": product_id})).json()["store_name"] is None
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product_id, "use_store_credit": True})
    assert resp.status_code == 409 and "own credits" in resp.json()["detail"]
    assert await credit_balance(db, user_id) == before


async def test_a_failed_try_on_gives_the_store_its_credit_back(client, db, monkeypatch):  # noqa: ANN001
    _instant(monkeypatch, fail=True)
    store, product = await _store_with_credits(client, db, 1)
    _, photo_id, product_id = await _shopper_picks(client, store, product)

    job = (await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product_id, "use_store_credit": True})).json()
    assert (await _poll_until_terminal(client, job["id"]))["status"] == "failed"

    row = await db.get(Store, store["id"])
    await db.refresh(row)
    assert row.tryon_credits == 1
    rows = (await db.execute(select(StoreTryOn).where(StoreTryOn.tryon_job_id == job["id"]))).scalars().all()
    assert len(rows) == 1 and rows[0].refunded is True
