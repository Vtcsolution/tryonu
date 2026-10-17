"""The browser extensions: connect a browser, try on a product from any shop
with your TryOnU credits, and (store owners) add a page's product to your store."""

from __future__ import annotations

import pytest

from app.ai.providers.base import TryOnOutput
from app.ai.providers.mock import MockTryOnProvider
from tests.conftest import credit_balance, register_and_login, small_jpeg_bytes
from tests.test_tryon import _poll_until_terminal, _upload_front_photo

PAGE = "https://www.ebay.com/itm/1234567890"
IMAGE = "https://i.ebayimg.com/images/g/abc/s-l1600.jpg"


@pytest.fixture(autouse=True)
def _offline(monkeypatch):  # noqa: ANN001, ANN202
    monkeypatch.setattr("app.api.v1.endpoints.extension.check_public_url", lambda url: None)

    async def fake_generate(self, payload):  # noqa: ANN001, ANN202, ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)


async def _connect(client, kind="shopper"):  # noqa: ANN001, ANN202
    resp = await client.post("/api/v1/extension/token", json={"kind": kind, "label": "Chrome on Windows"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    assert token.startswith("tou_ext_")
    return {"Authorization": f"Bearer {token}"}


async def test_a_photo_is_needed_first(client):  # noqa: ANN001
    data = await register_and_login(client)
    ext = await _connect(client)
    client.cookies.clear()
    me = (await client.get("/api/v1/extension/me", headers=ext)).json()
    assert me["email"] == data["user"]["email"] and me["has_photo"] is False and me["store"] is None
    resp = await client.post("/api/v1/extension/tryon", headers=ext, json={"image_url": IMAGE, "page_url": PAGE, "name": "Navy Chinos"})
    assert resp.status_code == 409


async def test_a_shopper_tries_on_a_product_from_any_shop_with_their_credits(client, db):  # noqa: ANN001
    from sqlalchemy import select

    from app.models.product import Product
    from app.services.queue import wait_for_inprocess_jobs

    data = await register_and_login(client)
    await _upload_front_photo(client)  # on the website
    ext = await _connect(client)
    client.cookies.clear()  # from here on, only the extension's token
    user_id = data["user"]["id"]
    me = (await client.get("/api/v1/extension/me", headers=ext)).json()
    assert me["has_photo"] is True
    before = await credit_balance(db, user_id)

    started = await client.post(
        "/api/v1/extension/tryon",
        headers=ext,
        json={"image_url": IMAGE, "page_url": PAGE, "name": "Navy Slim Chinos", "price_cents": 1914, "currency": "USD"},
    )
    assert started.status_code == 201, started.text
    job = started.json()
    assert job["product_name"] == "Navy Slim Chinos" and job["page_url"] == PAGE
    assert await credit_balance(db, user_id) == before - me["tryon_cost"]  # their normal credits

    await wait_for_inprocess_jobs()
    state = (await client.get(f"/api/v1/extension/tryon/{job['id']}", headers=ext)).json()
    assert state["status"] == "completed", state
    assert state["result_image_url"].startswith("http")

    saved = (await client.post(f"/api/v1/extension/tryon/{job['id']}/save", headers=ext)).json()
    assert saved["saved"] is True
    assert (await client.get("/api/v1/extension/tryons", headers=ext)).json()[0]["id"] == job["id"]

    # the page's product is never offered to other shoppers
    product = await db.scalar(select(Product).where(Product.product_url == PAGE))
    assert product is not None and product.is_active is False and product.merchant_name == "ebay.com"


async def test_a_disconnected_browser_is_refused(client):  # noqa: ANN001
    await register_and_login(client)
    ext = await _connect(client)
    assert (await client.get("/api/v1/extension/tokens")).json()[0]["label"] == "Chrome on Windows"
    assert (await client.delete("/api/v1/extension/tokens")).status_code == 204
    assert (await client.get("/api/v1/extension/me", headers=ext)).status_code == 401
    assert (await client.get("/api/v1/extension/me", headers={"Authorization": "Bearer tou_ext_nope"})).status_code == 401
    assert (await client.get("/api/v1/extension/me")).status_code == 401


async def test_a_store_owner_adds_a_pages_product_to_their_store(client, db):  # noqa: ANN001
    from sqlalchemy import select

    from app.models.store import StorePlan, StoreProduct

    plan = await db.scalar(select(StorePlan).where(StorePlan.code == "basic"))
    if plan is None:
        plan = StorePlan(code="basic", name="Basic", price_cents=1000, currency="usd", product_limit=50, duration_days=30, position=1)
        db.add(plan)
    plan.paypal_product_id = plan.paypal_plan_id = plan.paypal_plan_key = None
    plan.product_limit = 50
    await db.commit()

    await register_and_login(client)
    ext = await _connect(client, "store")
    product = {"name": "Pink Bridal Lehenga", "price_cents": 45000, "currency": "pkr", "product_url": "https://myshop.pk/p/lehenga", "image_url": "https://myshop.pk/img/lehenga.jpg", "category": "dresses", "gender": "women"}
    assert (await client.post("/api/v1/extension/store/products", headers=ext, json=product)).status_code == 404  # no store yet

    assert (await client.post("/api/v1/stores", json={"name": "Extension Couture", "country": "PK"})).status_code == 201
    assert (await client.post("/api/v1/extension/store/products", headers=ext, json=product)).status_code == 402  # no plan yet
    await client.post("/api/v1/stores/me/plans/basic/purchase")  # mock provider settles at once
    me = (await client.get("/api/v1/extension/me", headers=ext)).json()
    assert me["store"]["name"] == "Extension Couture" and me["store"]["plan_active"] is True

    added = await client.post("/api/v1/extension/store/products", headers=ext, json=product)
    assert added.status_code == 201, added.text
    assert added.json()["products"] == 1
    row = await db.scalar(select(StoreProduct).where(StoreProduct.id == added.json()["id"]))
    assert row.images == ["https://myshop.pk/img/lehenga.jpg"] and row.currency == "pkr"
    assert (await client.post("/api/v1/extension/store/products", headers=ext, json=product)).status_code == 409  # already there
