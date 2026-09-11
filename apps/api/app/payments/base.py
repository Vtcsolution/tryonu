"""Payment provider abstraction — mirrors the AI/retailer provider pattern
so Stripe can be swapped for another processor without touching the credit
ledger or API layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    external_payment_id: str
    status: str  # "succeeded" | "requires_action" | "pending"
    checkout_url: str | None = None
    client_secret: str | None = None


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    external_payment_id: str
    status: str  # "succeeded" | "failed"


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def create_checkout(
        self, *, amount_cents: int, currency: str, user_id: str, metadata: dict
    ) -> CheckoutResult: ...

    def verify_webhook(self, payload: bytes, signature: str | None) -> WebhookEvent:
        raise NotImplementedError
