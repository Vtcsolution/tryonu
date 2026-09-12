"""Stripe adapter — plain HTTP (no SDK dependency) against the PaymentIntents
API. create_checkout returns a client_secret the frontend confirms with
Stripe.js; the actual grant happens when /webhooks/stripe receives
payment_intent.succeeded (see api/v1/endpoints/webhooks.py) — a client
merely reporting success is never trusted.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import httpx
from fastapi import HTTPException, status

from app.payments.base import CheckoutResult, PaymentProvider, SubscriptionCheckoutResult, WebhookEvent

_API_BASE = "https://api.stripe.com/v1"

_EVENT_STATUS_MAP = {
    "payment_intent.succeeded": "succeeded",
    "payment_intent.payment_failed": "failed",
    "invoice.payment_succeeded": "subscription_renewed",
    "invoice.payment_failed": "subscription_payment_failed",
    "customer.subscription.deleted": "subscription_canceled",
    "customer.subscription.updated": "subscription_updated",
}


class StripePaymentProvider(PaymentProvider):
    name = "stripe"

    def __init__(self, *, secret_key: str, webhook_secret: str | None) -> None:
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret

    async def create_checkout(
        self, *, amount_cents: int, currency: str, user_id: str, metadata: dict
    ) -> CheckoutResult:
        form = {
            "amount": amount_cents,
            "currency": currency,
            "automatic_payment_methods[enabled]": "true",
            "metadata[user_id]": user_id,
        }
        for k, v in metadata.items():
            form[f"metadata[{k}]"] = str(v)

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{_API_BASE}/payment_intents",
                auth=(self._secret_key, ""),
                data=form,
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {resp.text}"
            )
        data = resp.json()
        return CheckoutResult(
            external_payment_id=data["id"],
            status="requires_action",
            client_secret=data["client_secret"],
        )

    async def create_subscription(
        self,
        *,
        price_cents: int,
        currency: str,
        interval: str,
        product_name: str,
        user_id: str,
        customer_email: str,
        metadata: dict,
    ) -> SubscriptionCheckoutResult:
        async with httpx.AsyncClient(timeout=20) as client:
            customer_id = await self._find_or_create_customer(client, email=customer_email, user_id=user_id)

            form = {
                "customer": customer_id,
                "items[0][price_data][currency]": currency,
                "items[0][price_data][unit_amount]": price_cents,
                "items[0][price_data][recurring][interval]": interval,
                "items[0][price_data][product_data][name]": product_name,
                # default_incomplete + expanding the PaymentIntent is the
                # same "hand back a client_secret, don't assume success"
                # pattern as one-off checkout — the subscription only
                # actually activates once the webhook confirms the first
                # invoice was paid (see api/v1/endpoints/webhooks.py).
                "payment_behavior": "default_incomplete",
                "expand[]": "latest_invoice.payment_intent",
                "metadata[user_id]": user_id,
            }
            for k, v in metadata.items():
                form[f"metadata[{k}]"] = str(v)

            resp = await client.post(f"{_API_BASE}/subscriptions", auth=(self._secret_key, ""), data=form)

        if resp.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {resp.text}")

        data = resp.json()
        payment_intent = (data.get("latest_invoice") or {}).get("payment_intent") or {}
        return SubscriptionCheckoutResult(
            external_subscription_id=data["id"],
            status="requires_action",
            client_secret=payment_intent.get("client_secret"),
        )

    async def cancel_subscription(self, external_subscription_id: str) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.delete(
                f"{_API_BASE}/subscriptions/{external_subscription_id}", auth=(self._secret_key, "")
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {resp.text}")

    async def _find_or_create_customer(self, client: httpx.AsyncClient, *, email: str, user_id: str) -> str:
        search = await client.get(
            f"{_API_BASE}/customers", auth=(self._secret_key, ""), params={"email": email, "limit": 1}
        )
        if search.status_code < 400:
            existing = search.json().get("data") or []
            if existing:
                return existing[0]["id"]

        created = await client.post(
            f"{_API_BASE}/customers",
            auth=(self._secret_key, ""),
            data={"email": email, "metadata[user_id]": user_id},
        )
        if created.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {created.text}")
        return created.json()["id"]

    def verify_webhook(self, payload: bytes, signature: str | None) -> WebhookEvent:
        if not self._webhook_secret or not signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing webhook signature")

        parts = dict(kv.split("=", 1) for kv in signature.split(",") if "=" in kv)
        timestamp, sig = parts.get("t"), parts.get("v1")
        if not timestamp or not sig:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed Stripe-Signature header")

        signed_payload = f"{timestamp}.{payload.decode()}".encode()
        expected = hmac.new(self._webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")
        if abs(time.time() - int(timestamp)) > 300:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook timestamp too old")

        import json

        event = json.loads(payload)
        obj = event.get("data", {}).get("object", {})
        event_type = event.get("type", "")
        status_ = _EVENT_STATUS_MAP.get(event_type, "unknown")
        return WebhookEvent(external_payment_id=obj.get("id", ""), status=status_, event_type=event_type, object_data=obj)
