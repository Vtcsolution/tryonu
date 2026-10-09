from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.payments.base import CheckoutResult, PaymentProvider, PaymentsUnavailableError
from app.payments.mock import MockPaymentProvider
from app.payments.paypal_provider import PayPalPaymentProvider
from app.payments.stripe_provider import StripePaymentProvider


class UnavailablePaymentProvider(PaymentProvider):
    """Production with no real payment provider: every purchase is refused.
    The mock approves every purchase without payment, so in production it
    would hand out credits for free."""

    name = "unavailable"
    supports_subscriptions = False

    async def create_checkout(self, **_kwargs) -> CheckoutResult:  # noqa: ANN003
        raise PaymentsUnavailableError("payments are not set up on this server")


@lru_cache
def get_payment_provider() -> PaymentProvider:
    settings = get_settings()
    if settings.PAYMENT_PROVIDER == "stripe":
        return StripePaymentProvider(
            secret_key=settings.STRIPE_SECRET_KEY,  # type: ignore[arg-type]
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    if settings.PAYMENT_PROVIDER == "paypal":
        live = settings.PAYPAL_MODE == "live"
        site = str(settings.FRONTEND_URL).rstrip("/")
        return PayPalPaymentProvider(
            client_id=settings.PAYPAL_CLIENT_ID if live else settings.PAYPAL_SANDBOX_CLIENT_ID,
            client_secret=settings.PAYPAL_CLIENT_SECRET if live else settings.PAYPAL_SANDBOX_CLIENT_SECRET,
            mode=settings.PAYPAL_MODE,
            return_url=f"{site}/credits/paypal",
            cancel_url=f"{site}/credits/paypal",
        )
    if settings.ENV == "production":
        return UnavailablePaymentProvider()
    return MockPaymentProvider()
