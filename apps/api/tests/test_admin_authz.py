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


async def test_an_admin_sees_a_users_photos_plan_and_how_they_paid(client, db):  # noqa: ANN001
    """Everything needed to help someone, on one page: their photos, their store plan, and each payment's gateway."""

    from app.models.enums import PaymentStatus, PhotoKind
    from app.models.photo import UserPhoto
    from app.models.subscription import Payment
    from tests.conftest import make_admin

    member = await register_and_login(client)
    uid = member["user"]["id"]
    db.add(UserPhoto(user_id=uid, kind=PhotoKind.FRONT, storage_key="photos/x.jpg", url="/media/photos/x.jpg?exp=1&sig=a"))
    db.add(Payment(user_id=uid, amount_cents=499, currency="usd", status=PaymentStatus.SUCCEEDED, provider="paddle"))
    await db.commit()
    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    detail = (await client.get(f"/api/v1/admin/users/{uid}")).json()
    assert [p["kind"] for p in detail["photos"]] == ["front"]
    assert detail["payments"][0]["provider"] == "paddle"


async def test_a_stored_picture_comes_as_a_small_thumbnail_when_asked(client):  # noqa: ANN001
    """?w=240 on our own signed media link: a small JPEG for thumbnail strips, same signature check."""
    import io

    from PIL import Image

    from app.services.storage_service import get_storage

    buf = io.BytesIO()
    Image.new("RGB", (1200, 1800), (200, 120, 150)).save(buf, "JPEG")
    storage = get_storage()
    storage.put("tests/thumb-src.jpg", buf.getvalue(), "image/jpeg")
    url = storage.signed_url("tests/thumb-src.jpg")
    full = await client.get(url)
    small = await client.get(url + "&w=240")
    assert full.status_code == 200 and small.status_code == 200
    assert Image.open(io.BytesIO(small.content)).width == 240 and len(small.content) < len(full.content)
    forged = await client.get(url.replace("sig=", "sig=x") + "&w=240")
    assert forged.status_code == 403
