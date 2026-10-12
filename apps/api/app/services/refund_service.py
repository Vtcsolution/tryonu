"""Taking back what a refunded payment bought.

Used by the admin's Refund button and by PayPal's refund/chargeback webhooks.
Credits: as many of the package's credits as the user still has (spent ones
can't be taken back). A store plan: the plan's days come off its end date.
Each payment is reversed once.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditPackage
from app.models.enums import CreditReason, PaymentStatus
from app.models.subscription import Payment
from app.services import credit_service


async def reverse_payment(db: AsyncSession, payment: Payment, *, why: str) -> dict:
    """Marks the payment refunded and takes back what it bought. Returns what
    was taken back. Does nothing to a payment that isn't a successful one."""
    if payment.status != PaymentStatus.SUCCEEDED:
        return {"reversed": False}
    taken: dict = {"reversed": True, "credits_removed": 0, "plan_days_removed": 0}
    if payment.credit_package_id:
        package = await db.get(CreditPackage, payment.credit_package_id)
        balance = await credit_service.get_balance(db, payment.user_id)
        amount = min(package.credits if package else 0, balance)
        if amount > 0:
            await credit_service.debit(
                db,
                user_id=payment.user_id,
                amount=amount,
                reason=CreditReason.PURCHASE_REFUND,
                reference_type="payment_refund",
                reference_id=payment.id,
                note=f"Refunded: {why}"[:255],
            )
        taken["credits_removed"] = amount
    if payment.store_plan_id and payment.store_id:
        from app.models.store import Store, StorePlan

        store = await db.get(Store, payment.store_id)
        plan = await db.get(StorePlan, payment.store_plan_id)
        if store is not None and plan is not None and store.plan_expires_at is not None:
            store.plan_expires_at = store.plan_expires_at - timedelta(days=plan.duration_days)
            taken["plan_days_removed"] = plan.duration_days
    payment.status = PaymentStatus.REFUNDED
    await db.commit()
    return taken
