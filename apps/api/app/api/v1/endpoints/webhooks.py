from __future__ import annotations

from fastapi import APIRouter, Header, Request
from sqlalchemy import select

from app.core.deps import DbSession
from app.models.enums import CreditReason, PaymentStatus
from app.models.subscription import Payment
from app.payments.registry import get_payment_provider
from app.schemas.common import Message
from app.services import credit_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe", response_model=Message)
async def stripe_webhook(
    request: Request,
    db: DbSession,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    payload = await request.body()
    provider = get_payment_provider()
    event = provider.verify_webhook(payload, stripe_signature)

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
