"""The Developer API: other sites run TryOnU try-ons with a key and prepaid credits."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.ai.providers.base import TryOnOutput, TryOnProviderError
from app.ai.providers.mock import MockTryOnProvider
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.developer import DeveloperAccount, DeveloperCreditPack
from app.models.fashn_ledger import FashnCreditLedger, FashnLiveAuthorization
from app.services.fashn_guard import (
    DEVELOPER_POOL,
    DbCreditGuard,
    GuardRefused,
    _pool,
    authorization_phrase,
    close_authorizations,
    create_authorization,
)
from tests.conftest import credit_balance, make_admin, register_and_login, small_jpeg_bytes
from tests.test_tryon import _poll_until_terminal


@pytest.fixture(autouse=True)
async def _packs(db):  # noqa: ANN001, ANN202
    existing = set((await db.execute(select(DeveloperCreditPack.code))).scalars())
    for code, name, tryons, price, pos in (("starter", "Starter", 50, 3500, 1), ("growth", "Growth", 250, 15000, 2)):
        if code not in existing:
            db.add(DeveloperCreditPack(code=code, name=name, tryons=tryons, price_cents=price, currency="usd", position=pos))
    await db.commit()


def _instant(monkeypatch, *, fail=False):  # noqa: ANN001, ANN202
    async def fake_generate(self, payload):  # noqa: ANN001, ANN202, ARG001
        if fail:
            raise TryOnProviderError("broken", retryable=False)
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)


async def _developer(client, *, buy=True):  # noqa: ANN001, ANN202
    data = await register_and_login(client)
    resp = await client.post(
        "/api/v1/developers", json={"company_name": "Lahore Couture Online", "website": "https://lc.example.com"}
    )
    assert resp.status_code == 201, resp.text
    if buy:
        bought = (await client.post("/api/v1/developers/packs/starter/purchase")).json()
        assert bought["status"] == "succeeded" and bought["developer_tryons"] == 50
    made = (await client.post("/api/v1/developers/keys", json={"name": "Shop server"})).json()
    assert made["key"].startswith("tou_sk_")
    return data, made["key"]


def _files():  # noqa: ANN202
    return {
        "person_image": ("me.jpg", small_jpeg_bytes((400, 600)), "image/jpeg"),
        "garment_image": ("dress.jpg", small_jpeg_bytes((300, 400), color=(200, 40, 60)), "image/jpeg"),
    }


def _bearer(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


async def test_a_developer_signs_up_buys_credits_and_runs_a_try_on(client, db, monkeypatch):  # noqa: ANN001
    _instant(monkeypatch)
    data, key = await _developer(client)
    user_id = data["user"]["id"]
    shopper_credits = await credit_balance(db, user_id)

    started = await client.post("/api/v1/public/tryons", files=_files(), data={"reference": "order-123"}, headers=_bearer(key))
    assert started.status_code == 202, started.text
    body = started.json()
    assert body["credits_left"] == 49 and body["reference"] == "order-123"

    await _poll_until_terminal(client, body["id"])
    done = (await client.get(f"/api/v1/public/tryons/{body['id']}", headers={"X-API-Key": key})).json()
    assert done["status"] == "completed" and done["result_image_url"]
    assert (await client.get("/api/v1/public/credits", headers=_bearer(key))).json() == {"credits_left": 49}
    # the developer's own shopper credits are untouched
    assert await credit_balance(db, user_id) == shopper_credits

    usage = (await client.get("/api/v1/developers/usage")).json()
    assert usage[0]["id"] == body["id"] and usage[0]["status"] == "completed"
    keys = (await client.get("/api/v1/developers/keys")).json()
    assert "key" not in keys[0] and keys[0]["prefix"].startswith("tou_sk_")


async def test_no_credits_bad_keys_and_someone_elses_try_ons_are_refused(client, monkeypatch):  # noqa: ANN001
    _instant(monkeypatch)
    _, key = await _developer(client, buy=False)
    assert (await client.post("/api/v1/public/tryons", files=_files(), headers=_bearer(key))).status_code == 402
    assert (await client.post("/api/v1/public/tryons", files=_files(), headers=_bearer("tou_sk_nope"))).status_code == 401
    assert (await client.post("/api/v1/public/tryons", files=_files())).status_code == 401

    keys = (await client.get("/api/v1/developers/keys")).json()
    await client.delete(f"/api/v1/developers/keys/{keys[0]['id']}")
    assert (await client.get("/api/v1/public/credits", headers=_bearer(key))).status_code == 401  # revoked

    _, other_key = await _developer(client)
    mine = (await client.post("/api/v1/public/tryons", files=_files(), headers=_bearer(other_key))).json()
    from app.services.queue import wait_for_inprocess_jobs

    await wait_for_inprocess_jobs()  # the try-on finishes before the next sign-up (one SQLite file)
    _, third_key = await _developer(client)
    peek = await client.get(f"/api/v1/public/tryons/{mine['id']}", headers=_bearer(third_key))
    assert peek.status_code == 404


async def test_a_failed_try_on_gives_the_credit_back(client, monkeypatch):  # noqa: ANN001
    _instant(monkeypatch, fail=True)
    _, key = await _developer(client)
    started = (await client.post("/api/v1/public/tryons", files=_files(), headers=_bearer(key))).json()
    assert started["credits_left"] == 49
    await _poll_until_terminal(client, started["id"])
    done = (await client.get(f"/api/v1/public/tryons/{started['id']}", headers=_bearer(key))).json()
    assert done["status"] == "failed" and done["credits_used"] == 0
    assert (await client.get("/api/v1/public/credits", headers=_bearer(key))).json()["credits_left"] == 50


async def test_the_daily_cap_stops_try_ons_without_charging(client, monkeypatch):  # noqa: ANN001
    _instant(monkeypatch)
    _, key = await _developer(client)
    monkeypatch.setattr(get_settings(), "DEV_API_DAILY_TRYON_CAP", 0)
    resp = await client.post("/api/v1/public/tryons", files=_files(), headers=_bearer(key))
    assert resp.status_code == 429
    assert (await client.get("/api/v1/public/credits", headers=_bearer(key))).json()["credits_left"] == 50


async def test_developer_try_ons_spend_their_own_daily_allowance_never_the_operators(db):  # noqa: ANN001
    await close_authorizations(db)
    dev_ids = (
        await db.execute(select(FashnLiveAuthorization.id).where(FashnLiveAuthorization.created_by == DEVELOPER_POOL))
    ).scalars().all()
    if dev_ids:
        await db.execute(delete(FashnCreditLedger).where(FashnCreditLedger.authorization_id.in_(dev_ids)))
        await db.execute(delete(FashnLiveAuthorization).where(FashnLiveAuthorization.id.in_(dev_ids)))
        await db.commit()
    guard = DbCreditGuard(AsyncSessionLocal)

    # the shop's own try-ons still need the operator's approval
    with pytest.raises(GuardRefused):
        await guard.reserve(model="tryon-max", resolution="1k", mode="balanced", purpose="shop")

    token = _pool.set(DEVELOPER_POOL)
    try:
        reservation = await guard.reserve(model="tryon-max", resolution="1k", mode="balanced", purpose="api")
        assert reservation.credits > 0
    finally:
        _pool.reset(token)

    # and the developer allowance never blocks the operator from approving
    approved = await create_authorization(db, 2, authorization_phrase(2))
    assert approved.budget_credits == 2
    await close_authorizations(db)


async def test_admins_see_developers_and_adjust_credits(client, db):  # noqa: ANN001
    await _developer(client, buy=False)
    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    accounts = (await client.get("/api/v1/admin/developers")).json()
    target = accounts[0]
    changed = (await client.post(f"/api/v1/admin/developers/{target['id']}/credits", json={"amount": 25})).json()
    assert changed["credits"] == target["credits"] + 25
    assert (await db.get(DeveloperAccount, target["id"])) is not None


async def test_photos_can_be_sent_as_links(client, monkeypatch):  # noqa: ANN001
    from app.api.v1.endpoints import developers as endpoint

    _instant(monkeypatch)
    fetched = []

    def fake_fetch(url, *, max_bytes, timeout):  # noqa: ANN001, ANN202, ARG001
        fetched.append(url)
        return small_jpeg_bytes((300, 400))

    def fake_check(url):  # noqa: ANN001, ANN202 - no DNS in tests: refuse private hosts like the real check
        from app.services.safe_fetch import UnsafeURLError

        if "127.0.0.1" in url or "localhost" in url:
            raise UnsafeURLError("must point to a public internet address")
        return url

    monkeypatch.setattr(endpoint, "fetch_limited", fake_fetch)
    monkeypatch.setattr(endpoint, "check_public_url", fake_check)
    _, key = await _developer(client)
    resp = await client.post(
        "/api/v1/public/tryons",
        json={"person_image_url": "https://cdn.example.com/me.jpg", "garment_image_url": "https://cdn.example.com/dress.jpg"},
        headers=_bearer(key),
    )
    assert resp.status_code == 202, resp.text
    assert fetched == ["https://cdn.example.com/me.jpg", "https://cdn.example.com/dress.jpg"]
    private = await client.post(
        "/api/v1/public/tryons",
        json={"person_image_url": "http://127.0.0.1/x.jpg", "garment_image_url": "https://cdn.example.com/d.jpg"},
        headers=_bearer(key),
    )
    assert private.status_code == 400
