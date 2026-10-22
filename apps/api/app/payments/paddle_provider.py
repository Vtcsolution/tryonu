"""Paddle Billing: card, PayPal, Apple Pay and Google Pay in one checkout, with
Paddle as the seller of record (it handles sales tax and VAT worldwide).

Flow: create_checkout makes a Paddle transaction for exactly this purchase
(a one-off price, no catalog needed) and returns its checkout link, our /pay
page, where Paddle.js opens the checkout. When the customer has paid, the page
sends them to /credits/paypal?payment_id=..., which asks our API to confirm
(POST /credits/purchase/{id}/capture): Paddle itself is asked for the
transaction, and only a paid one for exactly this amount and currency counts.
Paddle's webhook (transaction.completed) does the same for customers who
close the tab, and the payment sweeper is the backup.

Keys come from Admin -> Settings (or .env); PADDLE_MODE picks sandbox or live.
Nothing here logs or returns a key."""

from __future__ import annotations

import hashlib
import hmac
import time

import httpx

from app.payments.base import CaptureResult, CheckoutResult, PaymentProvider, PaymentsUnavailableError

_HOSTS = {"sandbox": "https://sandbox-api.paddle.com", "live": "https://api.paddle.com"}
# paid: money taken, still being finalised; completed: done
_PAID = {"paid", "completed"}
_WAITING = {"draft", "ready", "billed"}
# a signed webhook older than this is refused (replays)
_WEBHOOK_TOLERANCE_SECONDS = 300


class PaddleError(Exception):
    """A Paddle request failed. Never carries a credential."""


def _error_text(resp: httpx.Response) -> str:
    try:
        error = resp.json().get("error") or {}
    except ValueError:
        return f"HTTP {resp.status_code}"
    return f"HTTP {resp.status_code} {error.get('code') or ''}".strip()


def verify_signature(payload: bytes, header: str | None, secret: str | None, *, now: float | None = None) -> bool:
    """Paddle-Signature: "ts=<unix>;h1=<hex HMAC-SHA256 of '<ts>:<raw body>'>"."""
    if not header or not secret:
        return False
    parts = dict(p.split("=", 1) for p in header.split(";") if "=" in p)
    ts, given = parts.get("ts"), parts.get("h1")
    if not ts or not given or not ts.isdigit():
        return False
    if abs((now or time.time()) - int(ts)) > _WEBHOOK_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{ts}:".encode() + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, given)


class PaddlePaymentProvider(PaymentProvider):
    name = "paddle"
    supports_subscriptions = False

    def __init__(
        self,
        *,
        api_key: str | None,
        mode: str,
        pay_url: str,
        webhook_secret: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self.mode = "live" if mode == "live" else "sandbox"
        self._base = _HOSTS[self.mode]
        self._pay_url = pay_url
        self.webhook_secret = webhook_secret
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        if not self._api_key:
            raise PaymentsUnavailableError(f"Paddle {self.mode} API key is not set")
        return httpx.AsyncClient(
            base_url=self._base,
            timeout=30,
            transport=self._transport,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )

    async def create_checkout(
        self, *, amount_cents: int, currency: str, user_id: str, metadata: dict  # noqa: ARG002
    ) -> CheckoutResult:
        payment_id = str(metadata["payment_id"])
        description = str(metadata.get("description") or "TryOnU credits")[:200]
        body = {
            "items": [
                {
                    "quantity": 1,
                    "price": {
                        "description": description,
                        "name": description,
                        "unit_price": {"amount": str(int(amount_cents)), "currency_code": currency.upper()},
                        # the price shown is the price paid: any tax is inside it
                        "tax_mode": "internal",
                        "product": {"name": description, "tax_category": "standard"},
                    },
                }
            ],
            "custom_data": {"payment_id": payment_id, "user_id": user_id},
            "checkout": {"url": f"{self._pay_url}?payment_id={payment_id}"},
        }
        async with self._client() as client:
            resp = await client.post("/transactions", json=body)
        if resp.status_code not in (200, 201):
            raise PaddleError(f"Paddle could not start the checkout: {_error_text(resp)}")
        data = resp.json().get("data") or {}
        url = (data.get("checkout") or {}).get("url")
        if not data.get("id") or not url:
            raise PaddleError("Paddle returned no checkout link")
        return CheckoutResult(external_payment_id=data["id"], status="requires_action", checkout_url=url)

    async def capture(self, external_payment_id: str, *, idempotency_key: str) -> CaptureResult:  # noqa: ARG002
        """Nothing to capture with Paddle: it takes the money in its checkout.
        Ask it what happened to this transaction."""
        async with self._client() as client:
            resp = await client.get(f"/transactions/{external_payment_id}")
        if resp.status_code != 200:
            raise PaddleError(f"Paddle could not find the payment: {_error_text(resp)}")
        data = resp.json().get("data") or {}
        status = str(data.get("status") or "")
        if status in _WAITING:
            return CaptureResult(status="not_approved")
        if status not in _PAID:
            return CaptureResult(status="failed")
        totals = (data.get("details") or {}).get("totals") or {}
        try:
            total = int(totals.get("total") or totals.get("grand_total") or 0)
        except (TypeError, ValueError):
            total = 0
        return CaptureResult(
            status="completed",
            amount_cents=total,
            currency=str(data.get("currency_code") or "").lower(),
            capture_id=data.get("id"),
        )
