"""PayPal Checkout (Orders v2) for one-off credit packages.

Flow: create_checkout makes an order and returns PayPal's approval link; the
shopper approves on PayPal and is sent back to /credits/paypal; that page asks
our API to capture the order (POST /credits/purchase/{payment_id}/capture).
Credits are granted only when the capture PayPal returns is COMPLETED for
exactly the package's price and currency. An approved but uncaptured order
takes no money, so a shopper who never comes back is never charged.

Sandbox and live keys both live in .env; PAYPAL_MODE picks which. Nothing
here logs or returns a key or token.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.payments.base import CaptureResult, CheckoutResult, PaymentProvider, PaymentsUnavailableError

_HOSTS = {"sandbox": "https://api-m.sandbox.paypal.com", "live": "https://api-m.paypal.com"}


class PayPalError(Exception):
    """A PayPal request failed. Never carries a credential."""


@dataclass
class _Token:
    value: str
    expires_at: float


def _money(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _cents(value: str) -> int:
    return round(float(value) * 100)


def _error_text(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return f"HTTP {resp.status_code}"
    issue = next((d.get("issue") for d in body.get("details") or [] if isinstance(d, dict) and d.get("issue")), None)
    return f"HTTP {resp.status_code} {body.get('name') or body.get('error') or ''} {issue or ''}".strip()


class PayPalPaymentProvider(PaymentProvider):
    name = "paypal"
    supports_subscriptions = False

    def __init__(
        self,
        *,
        client_id: str | None,
        client_secret: str | None,
        mode: str,
        return_url: str,
        cancel_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._base = _HOSTS["live" if mode == "live" else "sandbox"]
        self.mode = "live" if mode == "live" else "sandbox"
        self._return_url = return_url
        self._cancel_url = cancel_url
        self._transport = transport
        self._token: _Token | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=30, transport=self._transport)

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if not (self._client_id and self._client_secret):
            raise PaymentsUnavailableError(f"PayPal {self.mode} keys are not set")
        if self._token and self._token.expires_at > time.time() + 60:
            return self._token.value
        resp = await client.post(
            "/v1/oauth2/token",
            auth=(self._client_id, self._client_secret),
            data={"grant_type": "client_credentials"},
        )
        if resp.status_code != 200:
            raise PayPalError(f"PayPal sign-in failed: {_error_text(resp)}")
        body = resp.json()
        self._token = _Token(body["access_token"], time.time() + int(body.get("expires_in") or 300))
        return self._token.value

    async def create_checkout(
        self, *, amount_cents: int, currency: str, user_id: str, metadata: dict  # noqa: ARG002
    ) -> CheckoutResult:
        payment_id = str(metadata["payment_id"])
        async with self._client() as client:
            token = await self._access_token(client)
            resp = await client.post(
                "/v2/checkout/orders",
                headers={"Authorization": f"Bearer {token}", "PayPal-Request-Id": f"order-{payment_id}"},
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [
                        {
                            "reference_id": payment_id,
                            "custom_id": payment_id,
                            "description": str(metadata.get("description") or "TryOnU credits")[:127],
                            "amount": {"currency_code": currency.upper(), "value": _money(amount_cents)},
                        }
                    ],
                    "payment_source": {
                        "paypal": {
                            "experience_context": {
                                "brand_name": "TryOnU",
                                "user_action": "PAY_NOW",
                                "shipping_preference": "NO_SHIPPING",
                                "return_url": f"{self._return_url}?payment_id={payment_id}",
                                "cancel_url": f"{self._cancel_url}?payment_id={payment_id}&cancelled=1",
                            }
                        }
                    },
                },
            )
        if resp.status_code not in (200, 201):
            raise PayPalError(f"PayPal could not create the order: {_error_text(resp)}")
        body = resp.json()
        approve = next(
            (link["href"] for link in body.get("links") or [] if link.get("rel") in ("payer-action", "approve")), None
        )
        if not approve:
            raise PayPalError("PayPal returned no approval link")
        return CheckoutResult(external_payment_id=body["id"], status="requires_action", checkout_url=approve)

    async def capture(self, external_payment_id: str, *, idempotency_key: str) -> CaptureResult:
        async with self._client() as client:
            token = await self._access_token(client)
            headers = {"Authorization": f"Bearer {token}", "PayPal-Request-Id": f"capture-{idempotency_key}"}
            resp = await client.post(
                f"/v2/checkout/orders/{external_payment_id}/capture", headers={**headers, "Content-Type": "application/json"}
            )
            if resp.status_code == 422 and "ORDER_ALREADY_CAPTURED" in resp.text:
                resp = await client.get(f"/v2/checkout/orders/{external_payment_id}", headers=headers)
            if resp.status_code == 422 and "ORDER_NOT_APPROVED" in resp.text:
                return CaptureResult(status="not_approved")
        if resp.status_code not in (200, 201):
            raise PayPalError(f"PayPal could not capture the order: {_error_text(resp)}")
        body = resp.json()
        captures = [
            c for unit in body.get("purchase_units") or [] for c in ((unit.get("payments") or {}).get("captures") or [])
        ]
        if not captures:
            return CaptureResult(status="pending" if body.get("status") in ("APPROVED", "SAVED") else "failed")
        cap = captures[0]
        status = {"COMPLETED": "completed", "PENDING": "pending"}.get(cap.get("status"), "failed")
        amount = cap.get("amount") or {}
        return CaptureResult(
            status=status,
            amount_cents=_cents(amount["value"]) if amount.get("value") else None,
            currency=(amount.get("currency_code") or "").lower() or None,
            capture_id=cap.get("id"),
        )
