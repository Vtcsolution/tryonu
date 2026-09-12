from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Header, Request
from sqlalchemy import select

from app.core.deps import DbSession
from app.core.logging import logger
from app.core.time import utcnow
from app.models.enums import CreditReason, PaymentStatus, SubscriptionStatus
from app.models.subscription import Payment, Subscription
from app.payments.registry import get_payment_provider
from app.schemas.common import Message
from app.services import credit_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_STRIPE_SUBSCRIPTION_STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.TRIALING,
    "past_due": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "incomplete": SubscriptionStatus.INCOMPLETE,
    "incomplete_expired": SubscriptionStatus.CANCELED,
    "unpaid": SubscriptionStatus.PAST_DUE,
}


@router.post("/stripe", response_model=Message)
async def stripe_webhook(
    request: Request,
    db: DbSession,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    payload = await request.body()
    provider = get_payment_provider()
    event = provider.verify_webhook(payload, stripe_signature)

    if event.event_type == "invoice.payment_succeeded":
        await _handle_invoice_paid(db, event.object_data)
        return Message(detail="ok")

    if event.event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(db, event.object_data)
        return Message(detail="ok")

    if event.event_type == "customer.subscription.updated":
        await _handle_subscription_updated(db, event.object_data)
        return Message(detail="ok")

    # One-off credit-package payments (PaymentIntents) — unchanged from
    # before subscriptions existed.
    result = await db.execute(select(Payment).where(Payment.external_payment_id == event.external_payment_id))
    payment = result.scalar_one_or_none()
    if payment is None:
        # Unknown payment id — acknowledge so Stripe stops retrying, but do nothing.
        return Message(detail="ignored")

    if event.status == "succeeded" and payment.status != PaymentStatus.SUCCEEDED:
        payment.status = PaymentStatus.SUCCEEDED
        if payment.credit_package_id:
            from app.models.credit import CreditPackage

            package = await db.get(CreditPackage, payment.credit_package_id)
            if package:
                await credit_service.grant(
                    db,
                    user_id=payment.user_id,
                    amount=package.credits,
                    reason=CreditReason.PURCHASE,
                    reference_type="payment",
                    reference_id=payment.id,
                    note=f"Purchased {package.name} (webhook)",
                )
        await db.commit()
    elif event.status == "failed" and payment.status == PaymentStatus.PENDING:
        payment.status = PaymentStatus.FAILED
        await db.commit()

    return Message(detail="ok")


async def _find_subscription(db: DbSession, external_subscription_id: str | None) -> Subscription | None:
    if not external_subscription_id:
        return None
    result = await db.execute(
        select(Subscription).where(Subscription.external_subscription_id == external_subscription_id)
    )
    return result.scalar_one_or_none()


async def _handle_invoice_paid(db: DbSession, invoice: dict) -> None:
    """The single source of truth that a subscription cycle was actually
    paid for — this is what activates a brand-new subscription (it's
    created INCOMPLETE, see subscriptions.py) and what grants credits on
    every renewal. Never trust the client-side confirmation alone."""
    sub = await _find_subscription(db, invoice.get("subscription"))
    if sub is None:
        return

    was_first_invoice = sub.status == SubscriptionStatus.INCOMPLETE
    now = utcnow()
    sub.status = SubscriptionStatus.ACTIVE
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)

    # Idempotent per invoice id, not per subscription id — a retried
    # webhook for the same invoice must not double-grant, but next
    # month's invoice (a different id) must grant again.
    await credit_service.grant(
        db,
        user_id=sub.user_id,
        amount=sub.credits_per_cycle,
        reason=CreditReason.SUBSCRIPTION_GRANT,
        reference_type="subscription_invoice",
        reference_id=invoice.get("id") or f"{sub.id}:{now.isoformat()}",
        note="Subscription activated" if was_first_invoice else "Subscription renewed",
    )

    if was_first_invoice:
        payment_result = await db.execute(select(Payment).where(Payment.subscription_id == sub.id))
        payment = payment_result.scalars().first()
        if payment and payment.status != PaymentStatus.SUCCEEDED:
            payment.status = PaymentStatus.SUCCEEDED

    await db.commit()


async def _handle_subscription_deleted(db: DbSession, subscription_obj: dict) -> None:
    sub = await _find_subscription(db, subscription_obj.get("id"))
    if sub is None:
        return
    sub.status = SubscriptionStatus.CANCELED
    await db.commit()


async def _handle_subscription_updated(db: DbSession, subscription_obj: dict) -> None:
    sub = await _find_subscription(db, subscription_obj.get("id"))
    if sub is None:
        return
    new_status = _STRIPE_SUBSCRIPTION_STATUS_MAP.get(subscription_obj.get("status", ""))
    if new_status:
        sub.status = new_status
    await db.commit()


@router.api_route("/rakuten", methods=["GET", "POST"], response_model=Message)
async def rakuten_postback(request: Request):
    """Rakuten's Postback API for conversion/transaction reporting —
    typically a server-to-server GET (a "postback URL" with tracking
    params) or POST, fired when Rakuten attributes a sale to a click we
    referred. The exact parameter names (transaction id, mid, order id,
    commission amount, currency, ...) are NOT verified against a real
    Rakuten postback yet — no credentials or live traffic exist to
    confirm the real shape (same verification-status note as
    app/retailers/rakuten.py).

    For now this only logs the raw payload (both query params and, for a
    POST, the body) so nothing is lost, and always returns 200 — most
    postback systems only need acknowledgement, and a 4xx/5xx here would
    make Rakuten retry indefinitely for a param-name mismatch we can't yet
    diagnose without a real sample. Once a real postback payload is seen,
    this is the one place to add real parsing + a persisted conversion
    record — not invented ahead of time."""
    body = await request.body()
    logger.info(
        "rakuten_postback_received",
        query_params=dict(request.query_params),
        body=body.decode(errors="replace") if body else None,
    )
    return Message(detail="ok")
