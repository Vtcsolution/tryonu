"""Refunds, PayPal webhooks and FASHN approval from the admin panel. Offline: PayPal is faked."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.models.enums import PaymentStatus
from app.models.store import Store, StorePlan
from app.models.subscription import Payment
from app.payments.paypal_provider import PayPalPaymentProvider
from app.services.fashn_guard import close_authorizations
from tests.conftest import credit_balance, make_admin, register_and_login, seed_credit_package


class FakePayPal:
    """Orders, captures, refunds, subscriptions and webhook verification."""

    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.refunds = 0
        self.verify = "SUCCESS"
        self.subscription_status = "ACTIVE"
        self.subscription_custom_id: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "fake", "expires_in": 3600})
        if path == "/v2/checkout/orders":
            unit = json.loads(request.content)["purchase_units"][0]
            order_id = f"ORDER-{uuid.uuid4().hex[:10]}"  # unique, as PayPal's are
            self.orders[order_id] = unit
            return httpx.Response(201, json={"id": order_id, "links": [{"rel": "payer-action", "href": "https://paypal.test/pay"}]})
        if path.endswith("/capture"):
            order_id = path.split("/")[-2]
            amount = self.orders[order_id]["amount"]
            return httpx.Response(201, json={"id": order_id, "status": "COMPLETED", "purchase_units": [
                {"payments": {"captures": [{"id": f"CAP-{order_id}", "status": "COMPLETED", "amount": amount}]}}]})
        if path.startswith("/v2/checkout/orders/") and request.method == "GET":
            order_id = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": order_id, "purchase_units": [{"payments": {"captures": [{"id": f"CAP-{order_id}"}]}}]})
        if path.startswith("/v2/payments/captures/") and path.endswith("/refund"):
            self.refunds += 1
            return httpx.Response(201, json={"id": "REFUND-1", "status": "COMPLETED"})
        if path == "/v1/notifications/verify-webhook-signature":
            return httpx.Response(200, json={"verification_status": self.verify})
        if path == "/v1/billing/subscriptions/I-SUB1":
            return httpx.Response(200, json={"id": "I-SUB1", "status": self.subscription_status, "custom_id": self.subscription_custom_id,
                                             "billing_info": {"last_payment": {"amount": {"currency_code": "USD", "value": "10.00"}, "time": "2026-10-12T10:00:00Z"}}})
        return httpx.Response(404, json={"name": "RESOURCE_NOT_FOUND"})


@pytest.fixture
def paypal(monkeypatch):  # noqa: ANN001, ANN201
    fake = FakePayPal()
    provider = PayPalPaymentProvider(
        client_id="sandbox-id-not-real", client_secret="sandbox-secret-not-real", mode="sandbox",
        return_url="https://tryonu.test/r", cancel_url="https://tryonu.test/c", transport=httpx.MockTransport(fake),
    )
    for where in ("credits", "stores", "admin_ops"):
        monkeypatch.setattr(f"app.api.v1.endpoints.{where}.get_payment_provider", lambda *_a, **_k: provider)
    monkeypatch.setattr("app.api.v1.endpoints.webhooks.get_payment_provider", lambda *_a, **_k: provider)
    monkeypatch.setattr("app.services.payment_settlement.get_payment_provider", lambda *_a, **_k: provider)
    return fake


async def _paid_package(client, db):  # noqa: ANN001, ANN202
    await register_and_login(client)
    me = (await client.get("/api/v1/auth/me")).json()
    package = await seed_credit_package(db, name="Starter", credits=20, price_cents=700)
    started = (await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})).json()
    done = (await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")).json()
    assert done["status"] == "succeeded"
    return me, started["payment_id"]


async def _admin(client, db):  # noqa: ANN001, ANN202
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])


async def test_a_paypal_refund_returns_the_money_and_takes_back_the_credits_once(client, db, paypal):  # noqa: ANN001
    me, payment_id = await _paid_package(client, db)
    before = await credit_balance(db, me["id"])
    await _admin(client, db)

    refunded = (await client.post(f"/api/v1/admin/payments/{payment_id}/refund", json={"mode": "paypal"})).json()
    assert refunded["paypal_status"] == "COMPLETED" and refunded["credits_removed"] == 20 and paypal.refunds == 1
    assert await credit_balance(db, me["id"]) == before - 20
    again = await client.post(f"/api/v1/admin/payments/{payment_id}/refund", json={"mode": "paypal"})
    assert again.status_code == 409 and paypal.refunds == 1


async def test_a_refund_only_takes_back_credits_still_unspent(client, db, paypal):  # noqa: ANN001
    from app.models.user import User

    me, payment_id = await _paid_package(client, db)
    user = await db.get(User, me["id"])
    user.credits_balance = 5  # 15 of the 20 were spent on try-ons
    await db.commit()
    await _admin(client, db)
    refunded = (await client.post(f"/api/v1/admin/payments/{payment_id}/refund", json={"mode": "mark"})).json()
    assert refunded["credits_removed"] == 5 and paypal.refunds == 0  # "mark": PayPal not called
    assert await credit_balance(db, me["id"]) == 0


async def test_marking_a_store_plan_refunded_removes_its_days(client, db, paypal):  # noqa: ANN001
    await db.execute(delete(Store))
    if not await db.scalar(select(StorePlan).where(StorePlan.code == "basic")):
        db.add(StorePlan(code="basic", name="Basic", price_cents=1000, currency="usd", product_limit=50, duration_days=30, position=1))
    await db.commit()
    await register_and_login(client)
    await client.post("/api/v1/stores", json={"name": "Lahore Couture", "country": "PK"})
    started = (await client.post("/api/v1/stores/me/plans/basic/purchase")).json()
    await client.post(f"/api/v1/credits/purchase/{started['payment_id']}/capture")
    assert (await client.get("/api/v1/stores/me")).json()["plan_active"] is True
    await _admin(client, db)

    refunded = (await client.post(f"/api/v1/admin/payments/{started['payment_id']}/refund", json={"mode": "mark"})).json()
    assert refunded["plan_days_removed"] == 30
    store = await db.scalar(select(Store).where(Store.slug.like("lahore-couture%")))
    await db.refresh(store)
    from app.services.store_service import plan_active

    assert plan_active(store) is False


async def test_webhooks_are_ignored_unless_configured_and_verified(client, db, paypal, monkeypatch):  # noqa: ANN001
    me, payment_id = await _paid_package(client, db)
    paid = await credit_balance(db, me["id"])
    order_id = (await db.get(Payment, payment_id)).external_payment_id
    event = {"event_type": "PAYMENT.CAPTURE.REFUNDED", "resource": {"supplementary_data": {"related_ids": {"order_id": order_id}}}}
    headers = {k: "x" for k in ("paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id", "paypal-transmission-sig", "paypal-transmission-time")}

    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", None)
    assert (await client.post("/api/v1/webhooks/paypal", json=event, headers=headers)).json()["detail"] == "ignored"
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-TEST")
    paypal.verify = "FAILURE"
    assert (await client.post("/api/v1/webhooks/paypal", json=event, headers=headers)).json()["detail"] == "ignored"
    db.expire_all()
    assert (await db.get(Payment, payment_id)).status == PaymentStatus.SUCCEEDED

    paypal.verify = "SUCCESS"
    assert (await client.post("/api/v1/webhooks/paypal", json=event, headers=headers)).json()["detail"] == "ok"
    db.expire_all()
    assert (await db.get(Payment, payment_id)).status == PaymentStatus.REFUNDED
    assert await credit_balance(db, me["id"]) == paid - 20  # the package's credits taken back


async def test_a_verified_subscription_webhook_syncs_the_store(client, db, paypal, monkeypatch):  # noqa: ANN001
    await db.execute(delete(Store))
    if not await db.scalar(select(StorePlan).where(StorePlan.code == "basic")):
        db.add(StorePlan(code="basic", name="Basic", price_cents=1000, currency="usd", product_limit=50, duration_days=30, position=1))
    await db.commit()
    await register_and_login(client)
    created = (await client.post("/api/v1/stores", json={"name": "Karachi Kurta", "country": "PK"})).json()
    store = await db.get(Store, created["id"])
    store.subscription_id, store.subscription_plan_code, store.subscription_status = "I-SUB1", "basic", "APPROVAL_PENDING"
    await db.commit()
    paypal.subscription_custom_id = created["id"]
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-TEST")
    headers = {k: "x" for k in ("paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id", "paypal-transmission-sig", "paypal-transmission-time")}

    resp = await client.post(
        "/api/v1/webhooks/paypal", json={"event_type": "BILLING.SUBSCRIPTION.ACTIVATED", "resource": {"id": "I-SUB1"}}, headers=headers
    )
    assert resp.json()["detail"] == "ok"
    me = (await client.get("/api/v1/stores/me")).json()
    assert me["auto_renew"] is True and me["plan_active"] is True


async def test_admins_approve_fashn_credits_with_the_exact_phrase(client, db):  # noqa: ANN001
    await close_authorizations(db)
    await register_and_login(client)
    assert (await client.get("/api/v1/admin/fashn/approval")).status_code == 403
    await _admin(client, db)

    wrong = await client.post("/api/v1/admin/fashn/approval", json={"credits": 20, "hours": 24, "phrase": "AUTHORIZE 2 FASHN CREDITS"})
    assert wrong.status_code == 400
    ok = (await client.post("/api/v1/admin/fashn/approval", json={"credits": 20, "hours": 24, "phrase": "AUTHORIZE 20 FASHN CREDITS"})).json()
    assert ok["live_generation_allowed"] is True and ok["open_authorizations"][0]["budget"] == 20
    closed = (await client.post("/api/v1/admin/fashn/approval/close")).json()
    assert closed["open_authorizations"] == []  # closed, never deleted: the ledger points at it


# ------------------------------------------------------------------ paid, but never came back to our page


async def _started_package(client, db):  # noqa: ANN001, ANN202
    await register_and_login(client)
    me = (await client.get("/api/v1/auth/me")).json()
    package = await seed_credit_package(db, name="Starter", credits=20, price_cents=700)
    started = (await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})).json()
    return me, started["payment_id"]


async def test_the_sweep_finishes_a_payment_whose_shopper_closed_the_tab(client, db, paypal):  # noqa: ANN001
    from datetime import datetime, timedelta, timezone

    from app.services.payment_settlement import settle_pending_once

    me, payment_id = await _started_package(client, db)
    before = await credit_balance(db, me["id"])
    await settle_pending_once()  # too fresh: the shopper may still be on their way back
    assert await credit_balance(db, me["id"]) == before

    payment = await db.get(Payment, payment_id)
    payment.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db.commit()
    assert await settle_pending_once() >= 1
    assert await credit_balance(db, me["id"]) == before + 20
    await settle_pending_once()  # never twice
    assert await credit_balance(db, me["id"]) == before + 20
    # coming back later shows it as done
    assert (await client.post(f"/api/v1/credits/purchase/{payment_id}/capture")).json()["status"] == "succeeded"


async def test_a_verified_paypal_approval_webhook_adds_the_credits(client, db, paypal, monkeypatch):  # noqa: ANN001
    me, payment_id = await _started_package(client, db)
    before = await credit_balance(db, me["id"])
    order_id = (await db.get(Payment, payment_id)).external_payment_id
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-TEST")
    headers = {"paypal-transmission-id": "t", "paypal-transmission-time": "now", "paypal-transmission-sig": "s",
               "paypal-cert-url": "https://api.paypal.com/cert", "paypal-auth-algo": "SHA256withRSA"}
    event = {"event_type": "CHECKOUT.ORDER.APPROVED", "resource": {"id": order_id}}
    assert (await client.post("/api/v1/webhooks/paypal", json=event, headers=headers)).json()["detail"] == "ok"
    assert await credit_balance(db, me["id"]) == before + 20
    assert (await client.post("/api/v1/webhooks/paypal", json=event, headers=headers)).json()["detail"] == "ok"
    assert await credit_balance(db, me["id"]) == before + 20  # once
