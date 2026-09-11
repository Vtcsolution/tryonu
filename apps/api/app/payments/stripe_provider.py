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

from app.payments.base import CheckoutResult, PaymentProvider, WebhookEvent

_API_BASE = "https://api.stripe.com/v1"


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
        status_ = "succeeded" if event_type == "payment_intent.succeeded" else "failed"
        return WebhookEvent(external_payment_id=obj.get("id", ""), status=status_)
