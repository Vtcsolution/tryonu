"""Mock payment provider — "charges" succeed instantly, no card required.
Used automatically without STRIPE_SECRET_KEY so credit purchases are fully
testable without a payment account."""

from __future__ import annotations

import uuid

from app.payments.base import CheckoutResult, PaymentProvider, SubscriptionCheckoutResult


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    async def create_checkout(
        self, *, amount_cents: int, currency: str, user_id: str, metadata: dict
    ) -> CheckoutResult:
        return CheckoutResult(
            external_payment_id=f"mock_pay_{uuid.uuid4().hex[:12]}",
            status="succeeded",
        )

    async def create_subscription(self, **kwargs) -> SubscriptionCheckoutResult:
        return SubscriptionCheckoutResult(
            external_subscription_id=f"mock_sub_{uuid.uuid4().hex[:12]}",
            status="active",
        )

    async def cancel_subscription(self, external_subscription_id: str) -> None:
        return None
