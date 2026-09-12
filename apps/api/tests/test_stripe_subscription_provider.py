"""Locks in the real Stripe Subscriptions API request shape — no real
Stripe account needed, httpx is monkeypatched to a fake transport that
asserts on the outgoing requests and returns canned responses."""

from __future__ import annotations

import json

import httpx

from app.payments.stripe_provider import StripePaymentProvider


def _patch_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_create_subscription_uses_inline_price_data_and_default_incomplete(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/customers" and request.method == "GET":
            return httpx.Response(200, json={"data": []})
        if request.url.path == "/v1/customers" and request.method == "POST":
            return httpx.Response(200, json={"id": "cus_new123"})
        if request.url.path == "/v1/subscriptions":
            body = request.content.decode()
            captured["form"] = dict(p.split("=", 1) for p in body.split("&") if "=" in p)
            return httpx.Response(
                200,
                json={
                    "id": "sub_abc123",
                    "latest_invoice": {"payment_intent": {"client_secret": "pi_secret_xyz"}},
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    _patch_transport(monkeypatch, handler)

    provider = StripePaymentProvider(secret_key="sk_test", webhook_secret=None)
    result = await provider.create_subscription(
        price_cents=1999,
        currency="usd",
        interval="month",
        product_name="TryOnU Pro",
        user_id="user_1",
        customer_email="shopper@example.com",
        metadata={"plan": "pro"},
    )

    assert result.external_subscription_id == "sub_abc123"
    assert result.status == "requires_action"
    assert result.client_secret == "pi_secret_xyz"

    form = captured["form"]
    assert form["customer"] == "cus_new123"
    assert form["items%5B0%5D%5Bprice_data%5D%5Bunit_amount%5D"] == "1999"
    assert form["items%5B0%5D%5Bprice_data%5D%5Brecurring%5D%5Binterval%5D"] == "month"
    assert form["payment_behavior"] == "default_incomplete"


async def test_create_subscription_reuses_an_existing_customer_by_email(monkeypatch):
    create_customer_called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal create_customer_called
        if request.url.path == "/v1/customers" and request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "cus_existing"}]})
        if request.url.path == "/v1/customers" and request.method == "POST":
            create_customer_called = True
            return httpx.Response(200, json={"id": "cus_should_not_be_used"})
        if request.url.path == "/v1/subscriptions":
            body = request.content.decode()
            assert "customer=cus_existing" in body
            return httpx.Response(200, json={"id": "sub_1", "latest_invoice": {"payment_intent": {}}})
        raise AssertionError(f"unexpected request: {request.url}")

    _patch_transport(monkeypatch, handler)

    provider = StripePaymentProvider(secret_key="sk_test", webhook_secret=None)
    await provider.create_subscription(
        price_cents=799,
        currency="usd",
        interval="month",
        product_name="TryOnU Starter",
        user_id="user_2",
        customer_email="existing@example.com",
        metadata={},
    )
    assert create_customer_called is False


async def test_cancel_subscription_calls_delete_on_the_right_id(monkeypatch):
    deleted_path = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal deleted_path
        deleted_path = request.url.path
        return httpx.Response(200, json={"id": "sub_xyz", "status": "canceled"})

    _patch_transport(monkeypatch, handler)

    provider = StripePaymentProvider(secret_key="sk_test", webhook_secret=None)
    await provider.cancel_subscription("sub_xyz")
    assert deleted_path == "/v1/subscriptions/sub_xyz"


def test_invoice_payment_succeeded_webhook_carries_subscription_id():
    import hashlib
    import hmac
    import time

    secret = "whsec_x"
    provider = StripePaymentProvider(secret_key="sk_test", webhook_secret=secret)
    payload = json.dumps(
        {"type": "invoice.payment_succeeded", "data": {"object": {"id": "in_1", "subscription": "sub_9"}}}
    ).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload.decode()}".encode(), hashlib.sha256).hexdigest()

    event = provider.verify_webhook(payload, f"t={ts},v1={sig}")
    assert event.status == "subscription_renewed"
    assert event.object_data["subscription"] == "sub_9"
