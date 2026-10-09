"""Payment provider abstraction — mirrors the AI/retailer provider pattern
so Stripe can be swapped for another processor without touching the credit
ledger or API layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    external_payment_id: str
    status: str  # "succeeded" | "requires_action" | "pending"
    checkout_url: str | None = None
    client_secret: str | None = None


@dataclass(frozen=True, slots=True)
class CaptureResult:
    # "completed" (money taken) | "pending" (PayPal holding it) | "not_approved"
    # (shopper never approved) | "failed"
    status: str
    amount_cents: int | None = None
    currency: str | None = None
    capture_id: str | None = None


class PaymentsUnavailableError(Exception):
    """Purchases can't be taken right now (no usable payment provider).
    Never grant credits on this; tell the shopper to try later."""


@dataclass(frozen=True, slots=True)
class SubscriptionCheckoutResult:
    external_subscription_id: str
    status: str  # "active" (instant, e.g. mock) | "requires_action" (real Stripe — first invoice needs confirming)
    client_secret: str | None = None


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    external_payment_id: str
    status: str
    # "succeeded" | "failed" | "subscription_renewed" | "subscription_payment_failed"
    # | "subscription_canceled" | "subscription_updated" | "unknown"
    event_type: str = ""
    # Raw Stripe object for the event (invoice/subscription/payment_intent)
    # — handlers pull whatever fields that event type actually carries
    # rather than forcing every event through one rigid shape.
    object_data: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str
    #: whether recurring plans can be sold through this provider
    supports_subscriptions: bool = True

    @abstractmethod
    async def create_checkout(
        self, *, amount_cents: int, currency: str, user_id: str, metadata: dict
    ) -> CheckoutResult: ...

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
        raise NotImplementedError

    async def cancel_subscription(self, external_subscription_id: str) -> None:
        raise NotImplementedError

    async def capture(self, external_payment_id: str, *, idempotency_key: str) -> CaptureResult:
        """Take the money for an order the shopper approved (redirect providers
        such as PayPal). Providers that confirm on their own don't need it."""
        raise NotImplementedError

    def verify_webhook(self, payload: bytes, signature: str | None) -> WebhookEvent:
        raise NotImplementedError
