"""Admin control actions: every one is admin-gated, writes an audit row, and
actually changes behavior (a hidden product stops appearing in live
search, a suspended user is locked out immediately, ...) rather than
just flipping a flag nothing reads."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers.base import TryOnOutput
from app.ai.providers.mock import MockTryOnProvider
from app.main import app
from app.retailers.base import ProductProvider, RawProduct
from app.services.live_search_service import live_search
from app.services.product_ingestion_service import persist_single_product
from tests.conftest import credit_balance, make_admin, register_and_login, seed_product, small_jpeg_bytes


async def _login_as_new_admin(client, db) -> dict:
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])
    return data


async def _register_other_user(db) -> tuple[AsyncClient, dict]:
    """A second, independently-authenticated client — the shared `client`
    fixture only holds one session's cookies at a time."""
    other = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    data = await register_and_login(other)
    return other, data


class _FakeProvider(ProductProvider):
    def __init__(self, slug: str, items: list[RawProduct]):
        self.slug = slug
        self.display_name = slug.title()
        self._items = items

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:  # pragma: no cover
        return self._items

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        return self._items[:limit]


def _raw(pid: str) -> RawProduct:
    return RawProduct(
        retailer_product_id=pid,
        name=f"Item {pid}",
        price_cents=1000,
        product_url=f"https://example.com/{pid}",
        images=["https://example.com/img.jpg"],
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/admin/users/x"),
        ("patch", "/api/v1/admin/users/x"),
        ("post", "/api/v1/admin/users/x/credits"),
        ("post", "/api/v1/admin/tryon-jobs/x/cancel"),
        ("get", "/api/v1/admin/products"),
        ("patch", "/api/v1/admin/products/x"),
        ("patch", "/api/v1/admin/retailers/ebay"),
        ("get", "/api/v1/admin/credit-packages"),
        ("post", "/api/v1/admin/credit-packages"),
        ("patch", "/api/v1/admin/credit-packages/x"),
        ("get", "/api/v1/admin/system"),
        ("get", "/api/v1/admin/audit-log"),
    ],
)
async def test_admin_controls_reject_regular_users(client, method, path):
    await register_and_login(client)
    resp = await getattr(client, method)(path, **({"json": {}} if method in ("post", "patch") else {}))
    assert resp.status_code == 403


async def test_admin_can_grant_and_remove_credits_and_it_is_audited(client, db):
    other, target = await _register_other_user(db)
    await other.aclose()
    target_id = target["user"]["id"]
    await _login_as_new_admin(client, db)

    resp = await client.post(f"/api/v1/admin/users/{target_id}/credits", json={"amount": 50, "note": "goodwill"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["credits_balance"] == 150

    resp = await client.post(f"/api/v1/admin/users/{target_id}/credits", json={"amount": -30, "note": "abuse"})
    assert resp.status_code == 200
    assert resp.json()["credits_balance"] == 120

    detail = (await client.get(f"/api/v1/admin/users/{target_id}")).json()
    reasons = [t["reason"] for t in detail["recent_transactions"]]
    assert reasons.count("admin_adjustment") == 2

    log = (await client.get("/api/v1/admin/audit-log")).json()["items"]
    assert any(e["action"] == "user.credits" and e["target_id"] == target_id for e in log)


async def test_admin_credit_removal_cannot_go_negative(client, db):
    other, target = await _register_other_user(db)
    await other.aclose()
    await _login_as_new_admin(client, db)

    resp = await client.post(
        f"/api/v1/admin/users/{target['user']['id']}/credits", json={"amount": -5000, "note": "too much"}
    )
    assert resp.status_code == 402
    assert await credit_balance(db, target["user"]["id"]) == 100


async def test_suspending_a_user_locks_them_out_immediately(client, db):
    other, target = await _register_other_user(db)
    assert (await other.get("/api/v1/auth/me")).status_code == 200

    await _login_as_new_admin(client, db)
    resp = await client.patch(f"/api/v1/admin/users/{target['user']['id']}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    assert (await other.get("/api/v1/auth/me")).status_code == 401
    # and their refresh token can't sign them silently back in either
    assert (await other.post("/api/v1/auth/refresh")).status_code == 401
    await other.aclose()


async def test_admin_cannot_suspend_or_demote_themselves(client, db):
    me = await _login_as_new_admin(client, db)
    my_id = me["user"]["id"]
    assert (await client.patch(f"/api/v1/admin/users/{my_id}", json={"is_active": False})).status_code == 400
    assert (await client.patch(f"/api/v1/admin/users/{my_id}", json={"is_admin": False})).status_code == 400


async def test_admin_user_search_filters_by_email(client, db):
    other, target = await _register_other_user(db)
    await other.aclose()
    await _login_as_new_admin(client, db)

    email = target["user"]["email"]
    resp = await client.get("/api/v1/admin/users", params={"q": email})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == email


async def test_admin_tryon_job_list_loads_and_cancel_refunds(client, db, monkeypatch):
    """The admin job list used to lack the eager-loads TryOnJobOut needs
    (user_photo, wardrobe_item, outfit) — it would have errored on the
    first real job."""
    import asyncio

    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_generate(self, payload):  # noqa: ARG001
        started.set()
        await release.wait()
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="slow", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", slow_generate)

    other, target = await _register_other_user(db)
    files = {"file": ("front.jpg", small_jpeg_bytes(), "image/jpeg")}
    photo_id = (await other.post("/api/v1/photos", files=files, data={"kind": "front"})).json()["id"]
    product = await seed_product(db, name="Admin Cancel Target")
    job = (await other.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})).json()
    await other.aclose()

    await _login_as_new_admin(client, db)
    listed = await client.get("/api/v1/admin/tryon-jobs")
    assert listed.status_code == 200, listed.text
    row = next(j for j in listed.json()["items"] if j["id"] == job["id"])
    assert row["user_email"] == target["user"]["email"]

    resp = await client.post(f"/api/v1/admin/tryon-jobs/{job['id']}/cancel")
    release.set()
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
    assert await credit_balance(db, target["user"]["id"]) == 100


async def test_hidden_product_is_dropped_from_live_search_and_stays_hidden(client, db, monkeypatch):
    slug = f"shop-{uuid.uuid4().hex[:6]}"
    provider = _FakeProvider(slug, [_raw("keep"), _raw("hide")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [provider])

    saved = await persist_single_product(db, provider, _raw("hide"))
    await db.commit()

    await _login_as_new_admin(client, db)
    resp = await client.patch(f"/api/v1/admin/products/{saved.id}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    ids = {r.raw.retailer_product_id for r in await live_search("anything")}
    assert ids == {"keep"}

    # re-selecting the same item (or a sync touching it) must not un-hide it
    await persist_single_product(db, provider, _raw("hide"))
    await db.commit()
    await db.refresh(saved)
    assert saved.is_active is False


async def test_disabled_retailer_is_not_searched(client, db, monkeypatch):
    slug = f"shop-{uuid.uuid4().hex[:6]}"
    on = _FakeProvider(f"{slug}-on", [_raw("on1")])
    off = _FakeProvider(f"{slug}-off", [_raw("off1")])
    monkeypatch.setattr("app.services.live_search_service.get_all_providers", lambda: [on, off])
    monkeypatch.setattr("app.api.v1.endpoints.admin_controls.get_all_providers", lambda: [on, off])

    await _login_as_new_admin(client, db)
    resp = await client.patch(f"/api/v1/admin/retailers/{off.slug}", json={"is_active": False})
    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json() if r["slug"] == off.slug)
    assert row["is_active"] is False
    assert row["integration_built"] is True

    ids = {r.raw.retailer_product_id for r in await live_search("anything")}
    assert ids == {"on1"}


async def test_retailer_list_reports_stub_integrations_honestly(client, db):
    await _login_as_new_admin(client, db)
    rows = {r["slug"]: r for r in (await client.get("/api/v1/admin/retailers")).json()}
    assert rows["ebay"]["integration_built"] is True
    # amazon/daraz/flipkart are still unbuilt stubs — the panel must not
    # present them as working integrations
    for stub in ("amazon", "daraz", "flipkart"):
        assert rows[stub]["integration_built"] is False


async def test_admin_credit_packages_create_update_and_hide_from_shop(client, db):
    await _login_as_new_admin(client, db)
    name = f"Admin Pack {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/v1/admin/credit-packages", json={"name": name, "credits": 40, "price_cents": 399}
    )
    assert resp.status_code == 201, resp.text
    package = resp.json()

    public = (await client.get("/api/v1/credits/packages")).json()
    assert any(p["id"] == package["id"] for p in public)

    resp = await client.patch(
        f"/api/v1/admin/credit-packages/{package['id']}", json={"price_cents": 499, "is_active": False}
    )
    assert resp.status_code == 200
    assert resp.json()["price_cents"] == 499

    public = (await client.get("/api/v1/credits/packages")).json()
    assert all(p["id"] != package["id"] for p in public)


async def test_admin_system_status_never_exposes_secrets(client, db):
    await _login_as_new_admin(client, db)
    resp = await client.get("/api/v1/admin/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tryon_credit_cost"] == 5
    assert not any("key" in k.lower() or "secret" in k.lower() for k in body)
