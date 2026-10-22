from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.payments.base import CheckoutResult, PaymentProvider, PaymentsUnavailableError
from app.payments.mock import MockPaymentProvider
from app.payments.paddle_provider import PaddlePaymentProvider
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


GATEWAYS = ("paddle", "paypal", "stripe")
# what customers see for each choice
GATEWAY_LABELS = {"paddle": "Card, Apple Pay, Google Pay", "paypal": "PayPal", "stripe": "Card"}


def enabled_gateways() -> list[str]:
    """The gateways switched on in Admin, the one PAYMENT_PROVIDER names first."""
    settings = get_settings()
    on = [g for g in GATEWAYS if getattr(settings, f"{g.upper()}_ENABLED", False)]
    on.sort(key=lambda g: g != settings.PAYMENT_PROVIDER)
    return on


@lru_cache
def get_payment_provider(name: str | None = None) -> PaymentProvider:
    """A gateway by name (a payment already started always finishes with its own,
    switched on or not), or with no name the default one customers pay with."""
    settings = get_settings()
    if name is None:
        on = enabled_gateways()
        if on:
            name = on[0]
        elif settings.ENV == "production":
            return UnavailablePaymentProvider()
        else:
            return MockPaymentProvider()
    if name == "stripe":
        return StripePaymentProvider(
            secret_key=settings.STRIPE_SECRET_KEY,  # type: ignore[arg-type]
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    if name == "paypal":
        live = settings.PAYPAL_MODE == "live"
        site = str(settings.FRONTEND_URL).rstrip("/")
        return PayPalPaymentProvider(
            client_id=settings.PAYPAL_CLIENT_ID if live else settings.PAYPAL_SANDBOX_CLIENT_ID,
            client_secret=settings.PAYPAL_CLIENT_SECRET if live else settings.PAYPAL_SANDBOX_CLIENT_SECRET,
            mode=settings.PAYPAL_MODE,
            return_url=f"{site}/credits/paypal",
            cancel_url=f"{site}/credits/paypal",
        )
    if name == "paddle":
        live = settings.PADDLE_MODE == "live"
        return PaddlePaymentProvider(
            api_key=settings.PADDLE_API_KEY if live else settings.PADDLE_SANDBOX_API_KEY,
            mode=settings.PADDLE_MODE,
            pay_url=f"{str(settings.FRONTEND_URL).rstrip('/')}/pay",
            webhook_secret=settings.PADDLE_WEBHOOK_SECRET,
        )
    if name == "mock" and settings.ENV != "production":
        return MockPaymentProvider()
    return UnavailablePaymentProvider()


def checkout_provider(requested: str | None, lookup=None) -> PaymentProvider:  # noqa: ANN001
    """The gateway a buyer chose, if it's switched on; otherwise the default one.
    `lookup` is the caller's get_payment_provider (so a test can swap it)."""
    from fastapi import HTTPException, status

    lookup = lookup or get_payment_provider
    if requested:
        if requested not in enabled_gateways():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That payment method isn't available. Please choose another.")
        return lookup(requested)
    return lookup()
