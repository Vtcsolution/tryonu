"""A store's own page: customers order from their cart, the store gets the
order by email and the customer a ready WhatsApp message."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.email.registry import get_email_provider
from app.models.store import Store, StoreProduct
from tests.conftest import register_and_login


async def _store(client, db, *, whatsapp: str | None = "923001234567"):  # noqa: ANN001, ANN202
    await register_and_login(client)
    me = (await client.get("/api/v1/auth/me")).json()
    store = Store(
        owner_user_id=me["id"], name="Lahore Couture", slug=f"lahore-{uuid.uuid4().hex[:6]}", country="PK",
        status="approved", plan_code="starter", plan_expires_at=datetime.now(timezone.utc) + timedelta(days=20), plan_product_limit=50,
        contact_email="shop@example.com", whatsapp=whatsapp,
    )
    db.add(store)
    await db.flush()
    lawn = StoreProduct(store_id=store.id, external_id="lawn", name="Pink Lawn Suit", price_cents=500000, currency="pkr",
                        product_url="https://x.test/lawn", images=["https://x.test/lawn.jpg"])
    khussa = StoreProduct(store_id=store.id, external_id="khussa", name="Gold Khussa", price_cents=250000, currency="pkr",
                          product_url="https://x.test/khussa", images=["https://x.test/khussa.jpg"])
    db.add_all([lawn, khussa])
    await db.commit()
    return store, lawn, khussa


async def test_a_customer_orders_and_the_store_gets_it_by_email_and_whatsapp(client, db):  # noqa: ANN001
    store, lawn, khussa = await _store(client, db)
    sent = get_email_provider().sent
    before = len(sent)
    placed = await client.post(
        f"/api/v1/stores/public/{store.slug}/orders",
        json={
            "items": [{"product_id": lawn.id, "qty": 2}, {"product_id": khussa.id, "qty": 1}],
            "name": "Ayesha Khan", "phone": "03001112233", "email": "ayesha.order@example.com",
            "address": "House 5, Street 2, Gulberg", "city": "Lahore",
        },
    )
    assert placed.status_code == 201, placed.text
    body = placed.json()
    assert body["total_cents"] == 1250000 and body["number"].startswith("TU-")
    assert body["whatsapp_url"].startswith("https://wa.me/923001234567?text=") and "Pink%20Lawn%20Suit" in body["whatsapp_url"]
    to_store = [m for m in sent[before:] if m["to"] == "shop@example.com"]
    assert to_store and body["number"] in to_store[0]["subject"] and "Ayesha Khan" in to_store[0]["body"]
    assert any(m["to"] == "ayesha.order@example.com" for m in sent[before:])

    # the owner sees it and moves it along; the customer hears
    orders = (await client.get("/api/v1/stores/me/orders")).json()
    order = next(o for o in orders["items"] if o["number"] == body["number"])
    assert orders["new"] >= 1 and order["status"] == "new"
    before = len(sent)
    moved = await client.patch(f"/api/v1/stores/me/orders/{order['id']}", json={"status": "confirmed"})
    assert moved.status_code == 200 and moved.json()["status"] == "confirmed"
    assert any(m["to"] == "ayesha.order@example.com" and "confirmed" in m["subject"] for m in sent[before:])


async def test_prices_come_from_the_store_not_the_page_and_other_stores_products_are_refused(client, db):  # noqa: ANN001
    store, lawn, _ = await _store(client, db, whatsapp=None)
    _, other_lawn, _ = await _store(client, db)
    refused = await client.post(
        f"/api/v1/stores/public/{store.slug}/orders",
        json={"items": [{"product_id": other_lawn.id, "qty": 1}], "name": "Sana", "phone": "03001112233", "address": "House 1, Lahore"},
    )
    assert refused.status_code == 400
    ok = await client.post(
        f"/api/v1/stores/public/{store.slug}/orders",
        json={"items": [{"product_id": lawn.id, "qty": 1}], "name": "Sana", "phone": "03001112233", "address": "House 1, Lahore"},
    )
    assert ok.status_code == 201 and ok.json()["total_cents"] == 500000 and ok.json()["whatsapp_url"] is None


async def test_a_store_name_can_never_take_a_website_page(db):  # noqa: ANN001
    from app.services.store_service import unique_slug

    assert await unique_slug(db, "Try") == "try-store"
    assert await unique_slug(db, "Looks") == "looks-store"
