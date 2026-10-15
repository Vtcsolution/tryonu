"""Company stores: approval, plans, product limits, search with local stores
first, plan payment through PayPal, feed import and link safety. Offline."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.models.store import Store, StorePlan, StoreProduct
from app.payments.paypal_provider import PayPalPaymentProvider
from app.retailers.stores import StoreProductProvider
from app.services import store_service as svc
from app.services.safe_fetch import UnsafeURLError, check_public_url
from app.services.shopper_context import set_country
from tests.conftest import make_admin, register_and_login
from tests.test_paypal import FakePayPal

_LINK = "https://8.8.8.8/shop/item"  # a public address: no DNS needed offline


@pytest.fixture(autouse=True)
async def _clean(db):  # noqa: ANN001, ANN202
    await db.execute(delete(StoreProduct))
    await db.execute(delete(Store))
    for plan in (await db.execute(select(StorePlan))).scalars():
        plan.paypal_product_id = plan.paypal_plan_id = plan.paypal_plan_key = None
        plan.price_cents = {"basic": 1000, "standard": 2500}.get(plan.code, plan.price_cents)
    existing = set((await db.execute(select(StorePlan.code))).scalars())
    for code, name, price, limit, pos in (("basic", "Basic", 1000, 50, 1), ("standard", "Standard", 2500, 200, 2)):
        if code not in existing:
            db.add(StorePlan(code=code, name=name, price_cents=price, currency="usd", product_limit=limit, duration_days=30, position=pos))
    await db.commit()
    yield
    set_country(None)


async def _company(client, *, name="Lahore Couture", country="PK"):  # noqa: ANN001, ANN202
    await register_and_login(client)
    resp = await client.post("/api/v1/stores", json={"name": name, "country": country})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _product(client, name="Pink Bridal Lehenga"):  # noqa: ANN001, ANN202
    return await client.post(
        "/api/v1/stores/me/products",
        json={"name": name, "price_cents": 12000, "currency": "usd", "product_url": _LINK, "category": "Lehenga"},
    )


async def _approve(db, store_id):  # noqa: ANN001, ANN202
    store = await db.get(Store, store_id)
    store.status = "approved"
    await db.commit()


async def _with_photo(db, product_id):  # noqa: ANN001, ANN202
    product = await db.get(StoreProduct, product_id)
    product.images = ["https://8.8.8.8/photo.jpg"]
    await db.commit()


async def test_a_new_store_waits_for_approval_and_needs_a_plan_to_list_products(client, db):  # noqa: ANN001
    store = await _company(client)
    assert store["status"] == "pending" and store["plan_active"] is False and store["live"] is False
    assert (await _product(client)).status_code == 402  # no plan yet

    bought = await client.post("/api/v1/stores/me/plans/basic/purchase")  # mock provider settles at once
    assert bought.json()["status"] == "succeeded"
    me = (await client.get("/api/v1/stores/me")).json()
    assert me["plan_code"] == "basic" and me["plan_product_limit"] == 50 and me["plan_active"] is True
    assert me["live"] is False  # still waiting for the admin
    assert (await _product(client)).status_code == 201


async def test_the_plan_limits_how_many_products_a_store_lists(client, db):  # noqa: ANN001
    store = await _company(client)
    await client.post("/api/v1/stores/me/plans/basic/purchase")
    row = await db.get(Store, store["id"])
    row.plan_product_limit = 2
    await db.commit()
    assert (await _product(client, "Item one")).status_code == 201
    assert (await _product(client, "Item two")).status_code == 201
    third = await _product(client, "Item three")
    assert third.status_code == 403 and "allows 2 products" in third.json()["detail"]


async def test_shoppers_see_only_approved_paid_stores_and_their_own_country_first(client, db):  # noqa: ANN001
    us = await _company(client, name="New York Bridal", country="US")
    await client.post("/api/v1/stores/me/plans/basic/purchase")
    us_item = (await _product(client, "Pink Bridal Lehenga Gown")).json()
    pk = await _company(client, name="Lahore Couture", country="PK")
    await client.post("/api/v1/stores/me/plans/basic/purchase")
    pk_item = (await _product(client, "Pink Bridal Lehenga Embroidered")).json()
    for item in (us_item, pk_item):
        await _with_photo(db, item["id"])
    provider = StoreProductProvider()

    assert await provider.search_live(query="pink bridal lehenga", limit=10) == []  # not approved yet

    await _approve(db, us["id"])
    await _approve(db, pk["id"])
    (await db.get(Store, us["id"])).delivery = "worldwide"  # it ships to Pakistan too
    await db.commit()
    set_country("PK")
    found = await provider.search_live(query="women pink bridal lehenga", limit=10)
    assert [r.merchant_name for r in found] == ["Lahore Couture", "New York Bridal"]
    assert found[0].origin_country == "PK" and found[0].product_url == _LINK

    expired = await db.get(Store, pk["id"])
    expired.plan_expires_at = svc.utcnow() - timedelta(days=1)
    await db.commit()
    assert [r.merchant_name for r in await provider.search_live(query="pink lehenga", limit=10)] == ["New York Bridal"]


async def test_a_store_plan_paid_through_paypal_unlocks_on_capture(client, db, monkeypatch):  # noqa: ANN001
    provider = PayPalPaymentProvider(
        client_id="sandbox-id-not-real", client_secret="sandbox-secret-not-real", mode="sandbox",
        return_url="https://tryonu.test/credits/paypal", cancel_url="https://tryonu.test/credits/paypal",
        transport=httpx.MockTransport(FakePayPal()),
    )
    monkeypatch.setattr("app.api.v1.endpoints.stores.get_payment_provider", lambda: provider)
    monkeypatch.setattr("app.api.v1.endpoints.credits.get_payment_provider", lambda: provider)
    await _company(client)

    started = (await client.post("/api/v1/stores/me/plans/standard/purchase")).json()
    assert started["status"] == "requires_action" and started["checkout_url"]
    assert (await client.get("/api/v1/stores/me")).json()["plan_active"] is False

    done = (await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")).json()
    assert done["status"] == "succeeded" and done["plan_name"] == "Standard"
    me = (await client.get("/api/v1/stores/me")).json()
    assert me["plan_code"] == "standard" and me["plan_product_limit"] == 200 and me["plan_active"] is True


async def test_a_feed_imports_within_the_plan_limit_and_keeps_typed_in_products(client, db, monkeypatch):  # noqa: ANN001
    store = await _company(client)
    await client.post("/api/v1/stores/me/plans/basic/purchase")
    assert (await _product(client, "Typed In Kurta")).status_code == 201
    row = await db.get(Store, store["id"])
    row.plan_product_limit = 3
    await db.commit()
    feed = (
        "Handle,Title,Variant Price,Image Src,URL,Body (HTML)\n"
        "a,Pink Lehenga,120.00,https://8.8.8.8/a.jpg,https://8.8.8.8/p/a,Embroidered\n"
        "b,Gold Jhumka,25.00,https://8.8.8.8/b.jpg,https://8.8.8.8/p/b,\n"
        "c,No Photo Item,10.00,,https://8.8.8.8/p/c,\n"
        "d,Red Khussa,30.00,https://8.8.8.8/d.jpg,https://8.8.8.8/p/d,\n"
    )
    monkeypatch.setattr(svc, "fetch_limited", lambda url, max_bytes: feed.encode())
    assert (await client.put("/api/v1/stores/me/feed", json={"feed_url": "https://8.8.8.8/feed.csv"})).status_code == 200

    result = (await client.post("/api/v1/stores/me/feed/import")).json()["result"]
    assert "Imported 2 products" in result and "1 more didn't fit" in result and "1 rows skipped" in result
    names = [p["name"] for p in (await client.get("/api/v1/stores/me/products")).json()]
    assert "Typed In Kurta" in names and "Pink Lehenga" in names and len(names) == 3


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:6379/", "http://169.254.169.254/latest/meta-data", "http://10.0.0.5/feed.csv", "ftp://8.8.8.8/x", "file:///etc/passwd"],
)
def test_internal_or_non_web_links_are_refused(url):
    with pytest.raises(UnsafeURLError):
        check_public_url(url)


async def test_a_company_cannot_point_its_feed_at_our_own_server(client, db):  # noqa: ANN001
    await _company(client)
    resp = await client.put("/api/v1/stores/me/feed", json={"feed_url": "http://127.0.0.1:8000/admin"})
    assert resp.status_code == 400 and "public" in resp.json()["detail"]


async def test_only_admins_approve_stores_and_set_plan_prices(client, db):  # noqa: ANN001
    store = await _company(client)
    assert (await client.get("/api/v1/admin/stores")).status_code == 403
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])
    listed = (await client.get("/api/v1/admin/stores", params={"status_filter": "pending"})).json()
    assert any(s["id"] == store["id"] for s in listed)
    approved = await client.post(f"/api/v1/admin/stores/{store['id']}/status", json={"status": "approved"})
    assert approved.json()["status"] == "approved"
    plan = (await client.get("/api/v1/admin/stores/plans")).json()[0]
    updated = await client.patch(f"/api/v1/admin/stores/plans/{plan['id']}", json={"price_cents": 1500, "product_limit": 75})
    assert updated.json()["price_cents"] == 1500 and updated.json()["product_limit"] == 75


async def test_the_media_route_serves_store_photos_only(client):  # noqa: ANN001
    assert (await client.get("/api/v1/stores/media/users/someone/photo.jpg")).status_code == 404


async def _live_store_with_product(client, db, name="Lahore Couture", country="PK"):  # noqa: ANN001, ANN202
    store = await _company(client, name=name, country=country)
    await client.post("/api/v1/stores/me/plans/basic/purchase")
    product = (await _product(client)).json()
    await _with_photo(db, product["id"])
    await _approve(db, store["id"])
    return store, product


async def test_the_public_store_page_shows_live_stores_and_saves_a_product_for_try_on(client, db):  # noqa: ANN001
    store, product = await _live_store_with_product(client, db)
    page = (await client.get(f"/api/v1/stores/public/{store['slug']}")).json()
    assert page["name"] == "Lahore Couture" and [p["id"] for p in page["products"]] == [product["id"]]

    picked = await client.post(f"/api/v1/stores/public/{store['slug']}/products/{product['id']}/select")
    assert picked.status_code == 200
    saved = (await client.get(f"/api/v1/products/{picked.json()['product_id']}")).json()
    assert saved["merchant_name"] == "Lahore Couture" and saved["product_url"] == _LINK

    row = await db.get(Store, store["id"])
    row.status = "suspended"
    await db.commit()
    assert (await client.get(f"/api/v1/stores/public/{store['slug']}")).status_code == 404


async def test_a_company_sees_shop_clicks_on_its_products(client, db):  # noqa: ANN001
    from app.models.affiliate import AffiliateClick
    from app.models.enums import AffiliateSource
    from app.models.product import Product

    store, product = await _live_store_with_product(client, db)
    picked = (await client.post(f"/api/v1/stores/public/{store['slug']}/products/{product['id']}/select")).json()
    saved = await db.get(Product, picked["product_id"])
    db.add(AffiliateClick(product_id=saved.id, retailer_id=saved.retailer_id, source=AffiliateSource.STYLIST))
    await db.commit()

    stats = (await client.get("/api/v1/stores/me/stats")).json()
    assert stats["clicks"] == 1 and stats["top"][0]["name"] == "Pink Bridal Lehenga"


async def test_a_file_upload_adds_many_products_within_the_plan(client, db):  # noqa: ANN001
    store = await _company(client)
    await client.post("/api/v1/stores/me/plans/basic/purchase")
    row = await db.get(Store, store["id"])
    row.plan_product_limit = 2
    await db.commit()
    csv_text = (
        "id,name,price,image,url\n"
        "1,Pink Lehenga,120,https://8.8.8.8/a.jpg,https://8.8.8.8/p/1\n"
        "2,Gold Jhumka,25,https://8.8.8.8/b.jpg,https://8.8.8.8/p/2\n"
        "3,Red Khussa,30,https://8.8.8.8/c.jpg,https://8.8.8.8/p/3\n"
    )
    resp = await client.post(
        "/api/v1/stores/me/products/import-file", files={"file": ("products.csv", csv_text.encode(), "text/csv")}
    )
    assert "Added 2" in resp.json()["result"] and "1 more didn't fit" in resp.json()["result"]
    again = await client.post(
        "/api/v1/stores/me/products/import-file", files={"file": ("products.csv", csv_text.encode(), "text/csv")}
    )
    assert "updated 2" in again.json()["result"]  # same ids: updated, not duplicated


async def test_admins_see_a_store_in_detail_moderate_products_and_grant_a_plan(client, db, monkeypatch):  # noqa: ANN001
    sent = []

    async def capture(db, store, subject, body):  # noqa: ANN001, ANN202
        sent.append(subject)

    monkeypatch.setattr(svc, "notify_owner", capture)
    store, product = await _live_store_with_product(client, db)
    row = await db.get(Store, store["id"])
    row.status = "pending"
    await db.commit()
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])

    await client.post(f"/api/v1/admin/stores/{store['id']}/status", json={"status": "approved"})
    assert sent == ["Your TryOnU store is approved"]

    detail = (await client.get(f"/api/v1/admin/stores/{store['id']}")).json()
    assert detail["owner_email"] and [p["id"] for p in detail["products"]] == [product["id"]]
    assert detail["payments"][0]["plan_name"] == "Basic" and detail["stats"]["clicks"] == 0

    hidden = (await client.patch(f"/api/v1/admin/stores/{store['id']}/products/{product['id']}", json={"is_active": False})).json()
    assert hidden["products"][0]["is_active"] is False

    before = (await db.get(Store, store["id"])).plan_expires_at
    assert detail["plan_free"] is False  # bought Basic
    granted = (await client.post(f"/api/v1/admin/stores/{store['id']}/plan", json={"plan_code": "standard", "days": 30})).json()
    assert granted["plan_code"] == "standard" and granted["plan_product_limit"] == 200
    assert granted["plan_free"] is True
    await db.refresh(await db.get(Store, store["id"]))
    assert (await db.get(Store, store["id"])).plan_expires_at > before

    summary = (await client.get("/api/v1/admin/stores/summary")).json()
    assert summary["by_status"]["approved"] >= 1 and summary["live"] >= 1 and summary["plan_revenue"]

    ended = (await client.post(f"/api/v1/admin/stores/{store['id']}/plan/end")).json()
    assert ended["plan_active"] is False and ended["live"] is False


async def test_plan_reminders_go_out_once_per_expiry(client, db, monkeypatch):  # noqa: ANN001
    sent = []

    async def capture(db, store, subject, body):  # noqa: ANN001, ANN202
        sent.append(subject)

    monkeypatch.setattr(svc, "notify_owner", capture)
    store, _ = await _live_store_with_product(client, db)
    row = await db.get(Store, store["id"])
    row.plan_expires_at = svc.utcnow() + timedelta(days=2)
    await db.commit()

    await svc.send_plan_reminders(db)
    await svc.send_plan_reminders(db)
    assert sent == ["Your TryOnU store plan ends soon"]

    row.plan_expires_at = svc.utcnow() - timedelta(hours=1)
    await db.commit()
    await svc.send_plan_reminders(db)
    await svc.send_plan_reminders(db)
    assert sent[-1] == "Your TryOnU store plan has ended" and len(sent) == 2


class FakePayPalSubscriptions:
    """PayPal's catalog, billing-plan and subscription calls, in memory."""

    def __init__(self) -> None:
        self.plans_made = 0
        self.status = "APPROVAL_PENDING"
        self.custom_id: str | None = None
        self.last_payment: str | None = None
        self.cancelled = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        import json as _json

        path = request.url.path
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "fake", "expires_in": 3600})
        if path == "/v1/catalogs/products":
            return httpx.Response(201, json={"id": "PROD-1"})
        if path == "/v1/billing/plans":
            self.plans_made += 1
            return httpx.Response(201, json={"id": f"P-{self.plans_made}", "status": "ACTIVE"})
        if path == "/v1/billing/subscriptions" and request.method == "POST":
            self.custom_id = _json.loads(request.content)["custom_id"]
            return httpx.Response(
                201, json={"id": "I-SUB1", "status": "APPROVAL_PENDING", "links": [{"rel": "approve", "href": "https://paypal.test/approve/I-SUB1"}]}
            )
        if path == "/v1/billing/subscriptions/I-SUB1/cancel":
            self.cancelled = True
            self.status = "CANCELLED"
            return httpx.Response(204)
        if path == "/v1/billing/subscriptions/I-SUB1":
            billing = {"last_payment": {"amount": {"currency_code": "USD", "value": "10.00"}, "time": self.last_payment}} if self.last_payment else {}
            return httpx.Response(200, json={"id": "I-SUB1", "status": self.status, "plan_id": "P-1", "custom_id": self.custom_id, "billing_info": billing})
        return httpx.Response(404, json={"name": "RESOURCE_NOT_FOUND"})


@pytest.fixture
def paypal_subs(monkeypatch):  # noqa: ANN001, ANN201
    fake = FakePayPalSubscriptions()
    provider = PayPalPaymentProvider(
        client_id="sandbox-id-not-real", client_secret="sandbox-secret-not-real", mode="sandbox",
        return_url="https://tryonu.test/credits/paypal", cancel_url="https://tryonu.test/credits/paypal",
        transport=httpx.MockTransport(fake),
    )
    monkeypatch.setattr("app.api.v1.endpoints.stores.get_payment_provider", lambda: provider)
    return fake


async def test_auto_renew_unlocks_on_the_first_payment_and_extends_once_per_payment(client, db, paypal_subs):  # noqa: ANN001
    store = await _company(client)
    started = await client.post("/api/v1/stores/me/plans/basic/subscribe")
    assert started.json()["checkout_url"] == "https://paypal.test/approve/I-SUB1"
    assert paypal_subs.custom_id == store["id"]

    paypal_subs.status = "ACTIVE"  # approved, first payment not taken yet
    waiting = (await client.post("/api/v1/stores/me/subscription/sync")).json()
    assert waiting["result"] == "active" and waiting["store"]["plan_active"] is False

    paypal_subs.last_payment = "2026-10-12T10:00:00Z"
    first = (await client.post("/api/v1/stores/me/subscription/sync")).json()
    assert first["result"] == "renewed" and first["store"]["plan_active"] is True and first["store"]["auto_renew"] is True
    expiry = first["store"]["plan_expires_at"]
    again = (await client.post("/api/v1/stores/me/subscription/sync")).json()
    assert again["result"] == "active" and again["store"]["plan_expires_at"] == expiry  # the same payment, not twice

    paypal_subs.last_payment = "2026-11-11T10:00:00Z"  # next month's charge
    renewed = (await client.post("/api/v1/stores/me/subscription/sync")).json()
    assert renewed["result"] == "renewed" and renewed["store"]["plan_expires_at"] > expiry
    payments = (await client.get("/api/v1/stores/me/payments")).json()
    assert [p["status"] for p in payments] == ["succeeded", "succeeded"]


async def test_the_paypal_billing_plan_is_reused_until_the_price_changes(client, db, paypal_subs):  # noqa: ANN001
    await _company(client)
    await client.post("/api/v1/stores/me/plans/basic/subscribe")
    await client.post("/api/v1/stores/me/plans/basic/subscribe")
    assert paypal_subs.plans_made == 1
    plan = await db.scalar(select(StorePlan).where(StorePlan.code == "basic"))
    plan.price_cents = 1200
    await db.commit()
    await client.post("/api/v1/stores/me/plans/basic/subscribe")
    assert paypal_subs.plans_made == 2


async def test_turning_auto_renew_off_keeps_the_paid_time(client, db, paypal_subs):  # noqa: ANN001
    await _company(client)
    await client.post("/api/v1/stores/me/plans/basic/subscribe")
    paypal_subs.status, paypal_subs.last_payment = "ACTIVE", "2026-10-12T10:00:00Z"
    await client.post("/api/v1/stores/me/subscription/sync")

    off = (await client.post("/api/v1/stores/me/subscription/cancel")).json()
    assert paypal_subs.cancelled and off["auto_renew"] is False and off["plan_active"] is True


async def test_a_subscription_cancelled_on_paypal_turns_auto_renew_off(client, db, paypal_subs):  # noqa: ANN001
    await _company(client)
    await client.post("/api/v1/stores/me/plans/basic/subscribe")
    paypal_subs.status, paypal_subs.last_payment = "ACTIVE", "2026-10-12T10:00:00Z"
    await client.post("/api/v1/stores/me/subscription/sync")
    paypal_subs.status = "CANCELLED"
    stopped = (await client.post("/api/v1/stores/me/subscription/sync")).json()
    assert stopped["result"] == "stopped" and stopped["store"]["auto_renew"] is False and stopped["store"]["plan_active"] is True


async def test_a_subscription_made_for_another_store_is_never_counted(client, db, paypal_subs):  # noqa: ANN001
    await _company(client)
    await client.post("/api/v1/stores/me/plans/basic/subscribe")
    paypal_subs.custom_id = "someone-else"
    paypal_subs.status, paypal_subs.last_payment = "ACTIVE", "2026-10-12T10:00:00Z"
    result = (await client.post("/api/v1/stores/me/subscription/sync")).json()
    assert result["result"] == "mismatch" and result["store"]["plan_active"] is False


async def test_auto_renew_needs_paypal(client, db):  # noqa: ANN001
    await _company(client)  # the mock payment provider in tests
    resp = await client.post("/api/v1/stores/me/plans/basic/subscribe")
    assert resp.status_code == 400 and "PayPal" in resp.json()["detail"]


async def test_views_are_counted_when_products_are_shown(client, db):  # noqa: ANN001
    store, product = await _live_store_with_product(client, db)
    await client.get(f"/api/v1/stores/public/{store['slug']}")  # the public page shows it once
    await svc.record_views(db, [product["id"], product["id"], "not-a-product"])  # e.g. search results

    stats = (await client.get("/api/v1/stores/me/stats")).json()
    assert stats["views"] == 2  # one per product per page shown; duplicates in one page count once
    assert stats["top"][0]["views"] == 2 and stats["top"][0]["name"] == "Pink Bridal Lehenga"


async def test_a_plan_lets_a_store_feature_only_so_many_products(client, db):  # noqa: ANN001
    basic = await db.scalar(select(StorePlan).where(StorePlan.code == "basic"))
    basic.featured_limit = 2
    await db.commit()
    store, first = await _live_store_with_product(client, db)
    ids = [first["id"]]
    for name in ("Gold Jhumka Earrings", "Red Khussa"):
        made = (await _product(client, name)).json()
        await _with_photo(db, made["id"])
        ids.append(made["id"])

    for pid in ids[:2]:
        resp = await client.patch(f"/api/v1/stores/me/products/{pid}", json={"is_featured": True})
        assert resp.status_code == 200 and resp.json()["is_featured"] is True
    over = await client.patch(f"/api/v1/stores/me/products/{ids[2]}", json={"is_featured": True})
    assert over.status_code == 403 and "feature 2" in over.json()["detail"]

    mine = (await client.get("/api/v1/stores/me")).json()
    assert mine["featured_count"] == 2 and mine["plan_featured_limit"] == 2
    # featured products come first in the store's search, flagged for ranking
    set_country("PK")
    found = await StoreProductProvider().search_live(query="lehenga earrings khussa", limit=10)
    assert all(r.featured for r in found if r.retailer_product_id in ids[:2])
    basic.featured_limit = 0
    await db.commit()


async def test_featured_only_counts_up_to_the_current_plans_limit(client, db):  # noqa: ANN001
    store, product = await _live_store_with_product(client, db)
    row = await db.get(Store, store["id"])
    item = await db.get(StoreProduct, product["id"])
    item.is_featured = True
    row.plan_featured_limit = 0  # e.g. moved to a plan without featuring
    await db.commit()
    assert await svc.featured_ids(db, [row]) == set()
    row.plan_featured_limit = 5
    await db.commit()
    assert await svc.featured_ids(db, [row]) == {product["id"]}


async def test_shoppers_only_see_products_that_can_be_delivered_to_them(client, db):  # noqa: ANN001
    pk, item = await _live_store_with_product(client, db, name="Lahore Couture", country="PK")
    provider = StoreProductProvider()

    async def seen_from(country):  # noqa: ANN001, ANN202
        set_country(country)
        return [r.retailer_product_id for r in await provider.search_live(query="pink bridal lehenga", limit=10)]

    # a new store delivers in its own country only
    assert item["id"] in await seen_from("PK")
    assert item["id"] not in await seen_from("US")

    # the store adds countries it delivers to
    resp = await client.patch("/api/v1/stores/me", json={"delivery": "countries", "delivery_countries": ["us", "AE"]})
    assert resp.status_code == 200 and resp.json()["delivery_countries"] == ["AE", "US"]
    assert item["id"] in await seen_from("US") and item["id"] not in await seen_from("GB")

    # one product ships everywhere, whatever the store does
    await client.patch("/api/v1/stores/me", json={"delivery": "domestic"})
    await client.patch(f"/api/v1/stores/me/products/{item['id']}", json={"delivery": "worldwide"})
    assert item["id"] in await seen_from("GB")

    # and one product only at home even though the store ships worldwide
    await client.patch("/api/v1/stores/me", json={"delivery": "worldwide"})
    await client.patch(f"/api/v1/stores/me/products/{item['id']}", json={"delivery": "domestic"})
    assert item["id"] not in await seen_from("GB")

    # the public page says so instead of hiding it
    set_country("GB")
    page = (await client.get(f"/api/v1/stores/public/{pk['slug']}", headers={"cf-ipcountry": "GB"})).json()
    assert page["products"][0]["delivers_to_you"] is False

    # "countries" needs at least one country
    bad = await client.patch("/api/v1/stores/me", json={"delivery": "countries", "delivery_countries": []})
    assert bad.status_code == 422



async def test_foreign_product_names_are_found_by_english_prompts(client, db):  # noqa: ANN001
    """A store selling "Sandalias ..." shows for "women sandals", named so shoppers know what it is."""
    store = await _company(client, name="Zee Store", country="PK")
    await client.post("/api/v1/stores/me/plans/basic/purchase")
    names = {
        "Shoes Sandalias marca Top 3 para mujer en color marron": "women sandals",
        "Pendientes Tu Y Yo De Plata De Ley 5 Y 7 Mm.": "women earrings",
        "Vestido mujer estampado floral escote pico": "women dress",
        "Relojes de mujer Reloj de pulsera creativo": "women watch",
    }
    for name in names:
        made = (await _product(client, name)).json()
        await _with_photo(db, made["id"])
    await _approve(db, store["id"])
    set_country("PK")
    provider = StoreProductProvider()
    for name, query in names.items():
        found = await provider.search_live(query=query, limit=10)
        assert [r.name.split(" · ")[0] for r in found] == [name], query
    watch = (await provider.search_live(query="women watch", limit=10))[0]
    assert watch.name.endswith("· Watch")  # a wristwatch, not a bracelet
    sandals = (await provider.search_live(query="women sandals", limit=10))[0]
    assert sandals.name.endswith("· Sandals")


async def test_a_product_is_found_by_its_category_too(client, db):  # noqa: ANN001
    store = await _company(client, name="Zee Store", country="PK")
    await client.post("/api/v1/stores/me/plans/basic/purchase")
    made = (
        await client.post(
            "/api/v1/stores/me/products",
            json={"name": "Zara Pearl Studs", "price_cents": 2500, "currency": "usd", "product_url": _LINK, "category": "Earrings"},
        )
    ).json()
    await _with_photo(db, made["id"])
    await _approve(db, store["id"])
    set_country("PK")
    found = await StoreProductProvider().search_live(query="women earrings", limit=10)
    assert [r.retailer_product_id for r in found] == [made["id"]]
