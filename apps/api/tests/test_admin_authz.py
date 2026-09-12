"""Admin endpoints must be genuinely role-gated, not just hidden from the
frontend."""

from __future__ import annotations

from tests.conftest import make_admin, register_and_login


async def test_admin_overview_rejects_regular_users(client):
    await register_and_login(client)
    resp = await client.get("/api/v1/admin/overview")
    assert resp.status_code == 403


async def test_admin_overview_rejects_unauthenticated(client):
    resp = await client.get("/api/v1/admin/overview")
    assert resp.status_code == 401


async def test_admin_overview_works_for_admins(client, db):
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])

    resp = await client.get("/api/v1/admin/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_users" in body
    assert body["total_users"] >= 1


async def test_admin_user_list_is_admin_only(client, db):
    data = await register_and_login(client)
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 403

    await make_admin(db, data["user"]["id"])
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 200


async def test_admin_retailers_list_is_admin_only(client, db):
    data = await register_and_login(client)
    resp = await client.get("/api/v1/admin/retailers")
    assert resp.status_code == 403

    await make_admin(db, data["user"]["id"])
    resp = await client.get("/api/v1/admin/retailers")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_admin_payments_list_is_admin_only(client, db):
    data = await register_and_login(client)
    resp = await client.get("/api/v1/admin/payments")
    assert resp.status_code == 403

    await make_admin(db, data["user"]["id"])
    resp = await client.get("/api/v1/admin/payments")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_admin_subscriptions_list_is_admin_only(client, db):
    data = await register_and_login(client)
    resp = await client.get("/api/v1/admin/subscriptions")
    assert resp.status_code == 403

    await client.post("/api/v1/subscriptions/subscribe", json={"plan": "starter"})

    await make_admin(db, data["user"]["id"])
    resp = await client.get("/api/v1/admin/subscriptions")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["plan"] == "starter" for r in rows)


async def test_admin_overview_reports_revenue_by_source(client, db):
    data = await register_and_login(client)
    await client.post("/api/v1/subscriptions/subscribe", json={"plan": "pro"})
    await make_admin(db, data["user"]["id"])

    resp = await client.get("/api/v1/admin/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["revenue_cents_subscriptions_30d"] >= 1999
    assert body["revenue_cents_one_off_30d"] >= 0
