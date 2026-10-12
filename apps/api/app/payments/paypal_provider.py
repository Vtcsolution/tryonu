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
from datetime import datetime

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


    # ------------------------------------------------- subscriptions (store plans)
    # PayPal Subscriptions: a billing plan (price every N days) on a catalog
    # product; a subscription to it is approved once by the payer, then PayPal
    # charges them every period until it's cancelled.

    async def store_billing_plan(
        self, *, name: str, price_cents: int, currency: str, days: int,
        product_id: str | None, plan_id: str | None, plan_key: str | None,
    ) -> tuple[str, str, str]:
        """(product_id, plan_id, key) of a PayPal billing plan charging this price
        every `days` days, made only when nothing made earlier still matches."""
        key = f"{self.mode}|{price_cents}|{currency.lower()}|{days}"
        if product_id and plan_id and plan_key == key:
            return product_id, plan_id, key
        async with self._client() as client:
            token = await self._access_token(client)
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if not product_id or not (plan_key or "").startswith(f"{self.mode}|"):
                resp = await client.post(
                    "/v1/catalogs/products",
                    headers={**headers, "PayPal-Request-Id": f"product-{name}-{key}"[:100]},
                    json={"name": f"TryOnU {name} store plan"[:127], "type": "SERVICE", "category": "SOFTWARE"},
                )
                if resp.status_code not in (200, 201):
                    raise PayPalError(f"PayPal could not create the product: {_error_text(resp)}")
                product_id = resp.json()["id"]
            resp = await client.post(
                "/v1/billing/plans",
                headers={**headers, "PayPal-Request-Id": f"plan-{product_id}-{key}"[:100], "Prefer": "return=representation"},
                json={
                    "product_id": product_id,
                    "name": f"TryOnU {name}: every {days} days"[:127],
                    "status": "ACTIVE",
                    "billing_cycles": [
                        {
                            "frequency": {"interval_unit": "DAY", "interval_count": days},
                            "tenure_type": "REGULAR",
                            "sequence": 1,
                            "total_cycles": 0,
                            "pricing_scheme": {"fixed_price": {"value": _money(price_cents), "currency_code": currency.upper()}},
                        }
                    ],
                    "payment_preferences": {"auto_bill_outstanding": True, "payment_failure_threshold": 1},
                },
            )
        if resp.status_code not in (200, 201):
            raise PayPalError(f"PayPal could not create the billing plan: {_error_text(resp)}")
        return product_id, resp.json()["id"], key

    async def start_store_subscription(
        self, *, plan_id: str, custom_id: str, return_url: str, cancel_url: str
    ) -> tuple[str, str]:
        """(subscription_id, approval link) for a new subscription to plan_id."""
        async with self._client() as client:
            token = await self._access_token(client)
            resp = await client.post(
                "/v1/billing/subscriptions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "plan_id": plan_id,
                    "custom_id": custom_id,
                    "application_context": {
                        "brand_name": "TryOnU",
                        "user_action": "SUBSCRIBE_NOW",
                        "shipping_preference": "NO_SHIPPING",
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    },
                },
            )
        if resp.status_code not in (200, 201):
            raise PayPalError(f"PayPal could not start the subscription: {_error_text(resp)}")
        body = resp.json()
        approve = next((link["href"] for link in body.get("links") or [] if link.get("rel") == "approve"), None)
        if not approve:
            raise PayPalError("PayPal returned no approval link")
        return body["id"], approve

    async def store_subscription(self, subscription_id: str) -> dict:
        """What PayPal says about a subscription now: status, plan, owner
        reference and its latest payment (time, cents, currency)."""
        async with self._client() as client:
            token = await self._access_token(client)
            resp = await client.get(
                f"/v1/billing/subscriptions/{subscription_id}", headers={"Authorization": f"Bearer {token}"}
            )
        if resp.status_code != 200:
            raise PayPalError(f"PayPal could not read the subscription: {_error_text(resp)}")
        body = resp.json()
        last = (body.get("billing_info") or {}).get("last_payment") or {}
        amount = last.get("amount") or {}
        paid_at = None
        if last.get("time"):
            paid_at = datetime.fromisoformat(str(last["time"]).replace("Z", "+00:00"))
        return {
            "status": body.get("status"),
            "plan_id": body.get("plan_id"),
            "custom_id": body.get("custom_id"),
            "last_paid_at": paid_at,
            "last_paid_cents": _cents(amount["value"]) if amount.get("value") else None,
            "last_paid_currency": (amount.get("currency_code") or "").lower() or None,
        }

    async def cancel_store_subscription(self, subscription_id: str, reason: str) -> None:
        async with self._client() as client:
            token = await self._access_token(client)
            resp = await client.post(
                f"/v1/billing/subscriptions/{subscription_id}/cancel",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"reason": reason[:127]},
            )
        # 422 SUBSCRIPTION_STATUS_INVALID: already cancelled; nothing left to stop
        if resp.status_code not in (200, 204) and not (resp.status_code == 422 and "STATUS_INVALID" in resp.text):
            raise PayPalError(f"PayPal could not cancel the subscription: {_error_text(resp)}")


    # ----------------------------------------------------- refunds and webhooks

    async def refund_order(self, order_id: str, *, idempotency_key: str) -> str:
        """Refunds the whole captured amount of an order. Returns PayPal's refund
        status: COMPLETED, PENDING (being processed) or FAILED."""
        async with self._client() as client:
            token = await self._access_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.get(f"/v2/checkout/orders/{order_id}", headers=headers)
            if resp.status_code != 200:
                raise PayPalError(f"PayPal could not read the order: {_error_text(resp)}")
            captures = [
                c for unit in resp.json().get("purchase_units") or [] for c in ((unit.get("payments") or {}).get("captures") or [])
            ]
            if not captures:
                raise PayPalError("PayPal has no captured payment on this order to refund")
            resp = await client.post(
                f"/v2/payments/captures/{captures[0]['id']}/refund",
                headers={**headers, "Content-Type": "application/json", "PayPal-Request-Id": f"refund-{idempotency_key}"},
                json={},
            )
        if resp.status_code == 422 and "CAPTURE_FULLY_REFUNDED" in resp.text:
            return "COMPLETED"
        if resp.status_code not in (200, 201):
            raise PayPalError(f"PayPal could not refund: {_error_text(resp)}")
        return str(resp.json().get("status") or "PENDING")

    async def verify_webhook(self, *, headers: dict, event: dict, webhook_id: str) -> bool:
        """Asks PayPal whether this webhook call really came from PayPal for our webhook."""
        lowered = {k.lower(): v for k, v in headers.items()}
        body = {
            "auth_algo": lowered.get("paypal-auth-algo"),
            "cert_url": lowered.get("paypal-cert-url"),
            "transmission_id": lowered.get("paypal-transmission-id"),
            "transmission_sig": lowered.get("paypal-transmission-sig"),
            "transmission_time": lowered.get("paypal-transmission-time"),
            "webhook_id": webhook_id,
            "webhook_event": event,
        }
        if not all(body.values()):
            return False
        async with self._client() as client:
            token = await self._access_token(client)
            resp = await client.post(
                "/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
        return resp.status_code == 200 and resp.json().get("verification_status") == "SUCCESS"
