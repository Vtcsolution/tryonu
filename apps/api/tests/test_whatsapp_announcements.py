"""WhatsApp ordering for local stores, the help WhatsApp number, and admin
announcements to every member. Offline."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.notification import Notification
from app.services import whatsapp
from tests.conftest import make_admin, register_and_login
from tests.test_community import _as
from tests.test_stores import _clean, _live_store_with_product  # noqa: F401  (the fixture cleans stores)


def test_numbers_are_written_with_their_country_code():
    assert whatsapp.normalize("0300 1234567", "PK") == "923001234567"
    assert whatsapp.normalize("+92 (300) 123-4567") == "923001234567"
    assert whatsapp.normalize("0092 300 1234567") == "923001234567"
    assert whatsapp.normalize("  ") is None
    with pytest.raises(ValueError):
        whatsapp.normalize("12345", "PK")
    with pytest.raises(ValueError):
        whatsapp.normalize("0300 1234567", None)  # local number, unknown country
    assert whatsapp.chat_link("923001234567", "Hi there") == "https://wa.me/923001234567?text=Hi%20there"


async def test_shoppers_order_from_a_local_store_on_whatsapp(client, db):  # noqa: ANN001
    store, product = await _live_store_with_product(client, db)
    bad = await client.patch("/api/v1/stores/me", json={"whatsapp": "123"})
    assert bad.status_code == 422
    mine = (await client.patch("/api/v1/stores/me", json={"whatsapp": "0300 1234567"})).json()
    assert mine["whatsapp"] == "923001234567"  # a Pakistani store: the local way works
    page = (await client.get(f"/api/v1/stores/public/{store['slug']}")).json()
    assert page["whatsapp"] == "923001234567"

    picked = (await client.post(f"/api/v1/stores/public/{store['slug']}/products/{product['id']}/select")).json()
    pid = picked["product_id"]
    assert (await client.get(f"/api/v1/affiliate/order-options/{pid}")).json() == {"whatsapp": True}
    go = await client.get(f"/api/v1/affiliate/whatsapp/{pid}?source=tryon_result", follow_redirects=False)
    assert go.status_code == 302
    link = urlparse(go.headers["location"])
    assert link.netloc == "wa.me" and link.path == "/923001234567"
    message = parse_qs(link.query)["text"][0]
    assert "Lahore Couture" in message and "Pink Bridal Lehenga" in message and f"/stores/{store['slug']}" in message
    assert (await client.get("/api/v1/stores/me/stats")).json()["clicks"] == 1  # counted like a shop click

    # no WhatsApp: no button, and the link falls back to the store's own page
    await client.patch("/api/v1/stores/me", json={"whatsapp": ""})
    assert (await client.get(f"/api/v1/affiliate/order-options/{pid}")).json() == {"whatsapp": False}
    go = await client.get(f"/api/v1/affiliate/whatsapp/{pid}", follow_redirects=False)
    assert go.status_code == 302 and "wa.me" not in go.headers["location"]


async def test_the_help_whatsapp_number(client, monkeypatch):  # noqa: ANN001
    s = get_settings()
    monkeypatch.setattr(s, "SUPPORT_WHATSAPP", "")
    assert (await client.get("/api/v1/contact/info")).json() == {"whatsapp": None}
    monkeypatch.setattr(s, "SUPPORT_WHATSAPP", "+92 300 7654321")
    assert (await client.get("/api/v1/contact/info")).json() == {"whatsapp": "923007654321"}


async def test_admins_send_an_announcement_to_every_member(client, db):  # noqa: ANN001
    await register_and_login(client)
    member = dict(client.cookies)
    assert (await client.post("/api/v1/admin/announcements", json={"text": "Eid sale!"})).status_code == 403

    client.cookies.clear()
    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    outside = await client.post("/api/v1/admin/announcements", json={"text": "Look here", "url": "https://example.com/x"})
    assert outside.status_code == 422  # only TryOnU pages
    sent = await client.post(
        "/api/v1/admin/announcements",
        json={"text": "Eid sale:   20% more credits   this week!", "url": "https://tryonu.app/credits"},
    )
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert body["text"] == "Eid sale: 20% more credits this week!" and body["url"] == "/credits" and body["sent_to"] >= 2
    listed = (await client.get("/api/v1/admin/announcements")).json()
    assert listed["items"][0]["id"] == body["id"] and listed["members"] >= 2

    await _as(client, member)
    items = (await client.get("/api/v1/notifications")).json()["items"]
    assert items[0]["kind"] == "announcement"
    assert items[0]["text"] == "Eid sale: 20% more credits this week!" and items[0]["url"] == "/credits"
    rows = (await db.execute(select(Notification).where(Notification.kind == "announcement"))).scalars().all()
    assert len(rows) == body["sent_to"]
