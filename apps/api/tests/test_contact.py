"""The Contact page: anyone can write; admins read and close messages."""

from __future__ import annotations

from tests.conftest import make_admin, register_and_login


async def test_a_visitor_writes_and_an_admin_reads_and_closes_it(client, db):  # noqa: ANN001
    sent = await client.post(
        "/api/v1/contact",
        json={"name": "Ayesha", "email": "ayesha@example.com", "topic": "store", "message": "How do I open a store in Lahore?"},
    )
    assert sent.status_code == 201, sent.text
    assert (await client.post("/api/v1/contact", json={"name": "x", "email": "bad", "message": "short"})).status_code == 422

    assert (await client.get("/api/v1/admin/messages")).status_code in (401, 403)  # not for visitors
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])
    inbox = (await client.get("/api/v1/admin/messages")).json()
    mine = next(m for m in inbox if m["email"] == "ayesha@example.com")
    assert mine["topic_label"] == "Selling on TryOnU (stores)" and mine["handled_at"] is None
    assert (await client.get("/api/v1/admin/messages/count")).json()["open"] >= 1

    done = (await client.post(f"/api/v1/admin/messages/{mine['id']}/handled")).json()
    assert done["handled_at"] is not None
    assert all(m["id"] != mine["id"] for m in (await client.get("/api/v1/admin/messages")).json())
    assert any(m["id"] == mine["id"] for m in (await client.get("/api/v1/admin/messages?show=all")).json())
