"""Subscriptions: the mock/instant path (active today, no real Stripe key
needed) and the real-Stripe requires_action -> webhook-confirmed path
(credits only ever granted once the webhook says the invoice was actually
paid — never on the client's say-so)."""

from __future__ import annotations

import json

from app.payments.base import SubscriptionCheckoutResult
from tests.conftest import credit_balance, register_and_login


async def test_list_plans_returns_the_configured_plans(client):
    resp = await client.get("/api/v1/subscriptions/plans")
    assert resp.status_code == 200
    plans = {p["plan"]: p for p in resp.json()}
    assert plans["starter"]["credits_per_cycle"] == 100
    assert plans["pro"]["price_cents"] == 1999
    assert "free" not in plans  # not a subscribable plan


async def test_subscribe_with_mock_provider_activates_instantly_and_grants_credits(client, db):
    data = await register_and_login(client)
    user_id = data["user"]["id"]
    starting = data["user"]["credits_balance"]

    resp = await client.post("/api/v1/subscriptions/subscribe", json={"plan": "starter"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["subscription"]["status"] == "active"
    assert body["client_secret"] is None

    assert await credit_balance(db, user_id) == starting + 100

    me = await client.get("/api/v1/subscriptions/me")
    assert me.status_code == 200
    assert me.json()["plan"] == "starter"


async def test_cannot_subscribe_twice_while_active(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/subscriptions/subscribe", json={"plan": "starter"})
    assert resp.status_code == 201

    resp = await client.post("/api/v1/subscriptions/subscribe", json={"plan": "pro"})
    assert resp.status_code == 409


async def test_subscribe_to_unknown_plan_is_rejected(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/subscriptions/subscribe", json={"plan": "free"})
    assert resp.status_code == 400


async def test_cancel_marks_cancel_at_period_end_without_ending_immediately(client, db):
    await register_and_login(client)
    await client.post("/api/v1/subscriptions/subscribe", json={"plan": "starter"})

    resp = await client.post("/api/v1/subscriptions/cancel")
    assert resp.status_code == 200

    me = await client.get("/api/v1/subscriptions/me")
    assert me.json()["status"] == "active"  # still live until the period actually ends
    assert me.json()["cancel_at_period_end"] is True


async def test_cancel_without_a_subscription_is_404(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/subscriptions/cancel")
    assert resp.status_code == 404


def _fake_stripe_provider(monkeypatch, *, external_subscription_id: str):
    """A real StripePaymentProvider (so verify_webhook's actual HMAC logic
    runs unmodified) with only the outbound HTTP call to Stripe replaced —
    used for both the subscribe endpoint and the webhook endpoint, which
    must agree on the same webhook secret."""
    from app.payments.stripe_provider import StripePaymentProvider

    provider = StripePaymentProvider(secret_key="sk_test_unused", webhook_secret="whsec_test")

    async def fake_create_subscription(self, **kwargs):  # noqa: ARG001
        return SubscriptionCheckoutResult(
            external_subscription_id=external_subscription_id, status="requires_action", client_secret="seti_fake_secret"
        )

    monkeypatch.setattr(StripePaymentProvider, "create_subscription", fake_create_subscription)
    monkeypatch.setattr("app.api.v1.endpoints.subscriptions.get_payment_provider", lambda: provider)
    monkeypatch.setattr("app.api.v1.endpoints.webhooks.get_payment_provider", lambda: provider)
    return provider


def _sign(payload: bytes, secret: str) -> tuple[bytes, dict[str, str]]:
    import hashlib
    import hmac
    import time

    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload.decode()}".encode(), hashlib.sha256).hexdigest()
    return payload, {"Stripe-Signature": f"t={ts},v1={sig}"}


async def test_real_stripe_path_does_not_grant_credits_until_webhook_confirms(client, db, monkeypatch):
    _fake_stripe_provider(monkeypatch, external_subscription_id="sub_fake_123")

    data = await register_and_login(client)
    user_id = data["user"]["id"]
    starting = data["user"]["credits_balance"]

    resp = await client.post("/api/v1/subscriptions/subscribe", json={"plan": "pro"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["subscription"]["status"] == "incomplete"
    assert body["client_secret"] == "seti_fake_secret"

    # no credits yet — only a confirmed webhook can grant them
    assert await credit_balance(db, user_id) == starting

    me = await client.get("/api/v1/subscriptions/me")
    assert me.status_code == 200
    assert me.json() is None  # incomplete isn't a "live" subscription yet


async def test_invoice_payment_succeeded_webhook_activates_and_grants_once(client, db, monkeypatch):
    _fake_stripe_provider(monkeypatch, external_subscription_id="sub_fake_456")

    data = await register_and_login(client)
    user_id = data["user"]["id"]
    starting = data["user"]["credits_balance"]

    resp = await client.post("/api/v1/subscriptions/subscribe", json={"plan": "pro"})
    assert resp.status_code == 201

    payload, headers = _sign(
        json.dumps(
            {"type": "invoice.payment_succeeded", "data": {"object": {"id": "in_fake_1", "subscription": "sub_fake_456"}}}
        ).encode(),
        "whsec_test",
    )
    resp = await client.post("/api/v1/webhooks/stripe", content=payload, headers=headers)
    assert resp.status_code == 200, resp.text

    assert await credit_balance(db, user_id) == starting + 300  # pro plan credits_per_cycle

    me = await client.get("/api/v1/subscriptions/me")
    assert me.json()["status"] == "active"

    # a second delivery of the SAME invoice event must not double-grant
    resp = await client.post("/api/v1/webhooks/stripe", content=payload, headers=headers)
    assert resp.status_code == 200
    assert await credit_balance(db, user_id) == starting + 300


async def test_subscription_deleted_webhook_cancels_it(client, db, monkeypatch):
    provider = _fake_stripe_provider(monkeypatch, external_subscription_id="sub_del_1")

    async def instant_active(self, **kwargs):  # noqa: ARG001
        return SubscriptionCheckoutResult(external_subscription_id="sub_del_1", status="active")

    monkeypatch.setattr(type(provider), "create_subscription", instant_active)

    await register_and_login(client)
    await client.post("/api/v1/subscriptions/subscribe", json={"plan": "starter"})

    payload, headers = _sign(
        json.dumps({"type": "customer.subscription.deleted", "data": {"object": {"id": "sub_del_1"}}}).encode(),
        "whsec_test",
    )
    resp = await client.post("/api/v1/webhooks/stripe", content=payload, headers=headers)
    assert resp.status_code == 200

    me = await client.get("/api/v1/subscriptions/me")
    assert me.json() is None  # canceled is no longer a "live" subscription
