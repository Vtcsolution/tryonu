from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.payments.base import PaymentProvider
from app.payments.mock import MockPaymentProvider
from app.payments.stripe_provider import StripePaymentProvider


@lru_cache
def get_payment_provider() -> PaymentProvider:
    settings = get_settings()
    if settings.PAYMENT_PROVIDER == "stripe":
        return StripePaymentProvider(
            secret_key=settings.STRIPE_SECRET_KEY,  # type: ignore[arg-type]
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    return MockPaymentProvider()
