"""Finishing a one-off payment: ask the processor (PayPal) what was paid and,
for exactly the expected amount, give the customer what they bought: credits,
a store plan, or developer API try-ons. Once only: a payment that already
succeeded is returned as it is.

Used when the customer comes back from PayPal (POST /credits/purchase/{id}/capture),
when PayPal notifies us (webhooks), and by a sweep every few minutes that finishes
payments whose customer closed the tab before coming back (settle_pending_forever).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.credit import CreditPackage
from app.models.enums import CreditReason, PaymentStatus
from app.models.subscription import Payment
from app.payments.base import PaymentsUnavailableError
from app.payments.registry import get_payment_provider
from app.schemas.credit import PurchaseCreditsResponse
from app.services import credit_service

SWEEP_EVERY_SECONDS = 180
# a shopper who paid but didn't come back does so within minutes; abandoned
# checkouts aren't asked about for longer than this. A capture PayPal holds as
# PENDING (e.g. an eCheck) is finished by the PAYMENT.CAPTURE.COMPLETED webhook.
SWEEP_WINDOW = timedelta(hours=6)


async def settle(db: AsyncSession, payment: Payment) -> PurchaseCreditsResponse:
    """The caller has locked the payment row (SELECT ... FOR UPDATE)."""
    if payment.status == PaymentStatus.SUCCEEDED:
        return PurchaseCreditsResponse(
            payment_id=payment.id, status="succeeded", new_balance=await credit_service.get_balance(db, payment.user_id)
        )
    if payment.status != PaymentStatus.PENDING or not payment.external_payment_id:
        return PurchaseCreditsResponse(payment_id=payment.id, status="failed")

    provider = get_payment_provider()
    if provider.name != payment.provider:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This payment was made another way")
    try:
        result = await provider.capture(payment.external_payment_id, idempotency_key=payment.id)
    except PaymentsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not available right now. Please try again shortly.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — the processor was unreachable; the payment stays pending
        logger.warning("payment_capture_failed", payment_id=payment.id, error=str(exc)[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="We couldn't confirm the payment yet. Please try again in a moment.",
        ) from exc

    if result.status in ("pending", "not_approved"):
        return PurchaseCreditsResponse(payment_id=payment.id, status="pending")
    matches = result.amount_cents == payment.amount_cents and (result.currency or "") == payment.currency.lower()
    if result.status != "completed" or not matches:
        payment.status = PaymentStatus.FAILED
        await db.commit()
        logger.warning(
            "payment_capture_rejected", payment_id=payment.id, status=result.status, amount_matches=matches
        )
        return PurchaseCreditsResponse(payment_id=payment.id, status="failed")

    if payment.developer_pack_id:
        # a developer API pack: try-ons added to the developer account
        from app.models.developer import DeveloperAccount, DeveloperCreditPack

        pack = await db.get(DeveloperCreditPack, payment.developer_pack_id)
        account = await db.get(DeveloperAccount, payment.developer_account_id) if payment.developer_account_id else None
        payment.status = PaymentStatus.SUCCEEDED
        if pack is not None and account is not None:
            account.credits += pack.tryons
        else:
            logger.error("payment_developer_pack_missing", payment_id=payment.id)
        await db.commit()
        return PurchaseCreditsResponse(
            payment_id=payment.id, status="succeeded", developer_tryons=pack.tryons if pack else None
        )

    if payment.store_plan_id:
        # a company's store plan: unlock (or extend) its 30-day pass
        from app.models.store import Store, StorePlan
        from app.services.store_service import activate_plan

        plan = await db.get(StorePlan, payment.store_plan_id)
        store = await db.get(Store, payment.store_id) if payment.store_id else None
        payment.status = PaymentStatus.SUCCEEDED
        if plan is not None and store is not None:
            activate_plan(store, plan)
            # share and earn: whoever invited this store's owner earns by plan
            from app.services.referral_service import reward_store_plan

            await reward_store_plan(db, store.owner_user_id, plan)
        else:
            logger.error("payment_store_plan_missing", payment_id=payment.id)
        await db.commit()
        return PurchaseCreditsResponse(
            payment_id=payment.id,
            status="succeeded",
            plan_name=plan.name if plan else None,
            plan_expires_at=store.plan_expires_at if store else None,
        )

    package = await db.get(CreditPackage, payment.credit_package_id) if payment.credit_package_id else None
    if package is None:
        # paid, but for a package that no longer exists: keep the money on
        # record as succeeded and leave the credits to support
        payment.status = PaymentStatus.SUCCEEDED
        await db.commit()
        logger.error("payment_package_missing", payment_id=payment.id)
        return PurchaseCreditsResponse(payment_id=payment.id, status="succeeded")
    payment.status = PaymentStatus.SUCCEEDED
    entry = await credit_service.grant(
        db,
        user_id=payment.user_id,
        amount=package.credits,
        reason=CreditReason.PURCHASE,
        reference_type="payment",
        reference_id=payment.id,
        note=f"Purchased {package.name}",
    )
    from app.services.notification_service import notify

    await notify(db, user_id=payment.user_id, kind="credits_added", credits=package.credits, text=package.name)
    await db.commit()
    return PurchaseCreditsResponse(
        payment_id=payment.id, status="succeeded", credits_granted=package.credits, new_balance=entry.balance_after
    )


async def settle_by_order_id(db: AsyncSession, order_id: str, provider: str = "paypal") -> PurchaseCreditsResponse | None:
    """PayPal (an order) or Paddle (a transaction) told us about a payment (a webhook): finish it."""
    payment = await db.scalar(
        select(Payment)
        .where(Payment.external_payment_id == order_id, Payment.provider == provider)
        .order_by(Payment.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if payment is None:
        return None
    try:
        return await settle(db, payment)
    except HTTPException:
        await db.rollback()
        return None


async def settle_pending_once() -> int:
    """Finish every recent PayPal or Paddle payment still pending: the customer
    paid but never came back to our page (closed the tab, lost connection)."""
    from app.db.session import AsyncSessionLocal

    provider = get_payment_provider()
    if provider.name not in ("paypal", "paddle"):
        return 0
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        ids = (
            await db.execute(
                select(Payment.id).where(
                    Payment.provider == provider.name,
                    Payment.status == PaymentStatus.PENDING,
                    Payment.external_payment_id.is_not(None),
                    Payment.created_at >= now - SWEEP_WINDOW,
                    # give the customer a moment to come back on their own first
                    Payment.created_at <= now - timedelta(minutes=2),
                )
            )
        ).scalars().all()
    done = 0
    for payment_id in ids:
        async with AsyncSessionLocal() as db:
            payment = await db.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
            if payment is None:
                continue
            try:
                result = await settle(db, payment)
            except HTTPException:
                await db.rollback()
                continue
            if result.status == "succeeded":
                done += 1
                logger.info("payment_settled_by_sweep", payment_id=payment_id)
    return done


async def settle_pending_forever() -> None:
    while True:
        await asyncio.sleep(SWEEP_EVERY_SECONDS)
        try:
            await settle_pending_once()
        except Exception as exc:  # noqa: BLE001 — never let the sweep die
            logger.warning("payment_sweep_failed", error=str(exc)[:200])
