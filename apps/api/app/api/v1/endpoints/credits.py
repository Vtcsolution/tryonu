from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.credit import CreditPackage
from app.models.enums import CreditReason, PaymentStatus
from app.models.subscription import Payment
from app.payments.registry import get_payment_provider
from app.schemas.credit import (
    CreditBalanceOut,
    CreditPackageOut,
    CreditTransactionOut,
    PurchaseCreditsRequest,
    PurchaseCreditsResponse,
)
from app.services import credit_service

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/balance", response_model=CreditBalanceOut)
async def balance(user: CurrentUser):
    return CreditBalanceOut(balance=user.credits_balance)


@router.get("/history", response_model=list[CreditTransactionOut])
async def history(user: CurrentUser, db: DbSession, limit: int = 50, offset: int = 0):
    from app.models.credit import CreditTransaction

    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get("/packages", response_model=list[CreditPackageOut])
async def packages(db: DbSession):
    result = await db.execute(select(CreditPackage).where(CreditPackage.is_active.is_(True)))
    return list(result.scalars().all())


@router.post("/purchase", response_model=PurchaseCreditsResponse)
async def purchase(payload: PurchaseCreditsRequest, user: CurrentUser, db: DbSession):
    package = await db.get(CreditPackage, payload.credit_package_id)
    if package is None or not package.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit package not found")

    provider = get_payment_provider()
    checkout = await provider.create_checkout(
        amount_cents=package.price_cents,
        currency=package.currency,
        user_id=user.id,
        metadata={"credit_package_id": package.id, "credits": package.credits},
    )

    payment = Payment(
        user_id=user.id,
        amount_cents=package.price_cents,
        currency=package.currency,
        status=PaymentStatus.SUCCEEDED if checkout.status == "succeeded" else PaymentStatus.PENDING,
        provider=provider.name,
        external_payment_id=checkout.external_payment_id,
        credit_package_id=package.id,
    )
    db.add(payment)
    await db.flush()

    if checkout.status != "succeeded":
        # Real Stripe path: the PaymentIntent needs client-side confirmation
        # (3DS, wallet, etc). The frontend confirms with client_secret via
        # Stripe.js, then polls GET /credits/purchase/{payment_id} — credits
        # are only ever granted server-side once Stripe's webhook reports
        # payment_intent.succeeded (see api/v1/endpoints/webhooks.py).
        # Never grant here based on what the client claims happened.
        await db.commit()
        return PurchaseCreditsResponse(
            payment_id=payment.id,
            status=checkout.status,
            client_secret=checkout.client_secret,
            checkout_url=checkout.checkout_url,
        )

    entry = await credit_service.grant(
        db,
        user_id=user.id,
        amount=package.credits,
        reason=CreditReason.PURCHASE,
        reference_type="payment",
        reference_id=payment.id,
        note=f"Purchased {package.name}",
    )
    await db.commit()
    return PurchaseCreditsResponse(
        payment_id=payment.id,
        status="succeeded",
        credits_granted=package.credits,
        new_balance=entry.balance_after,
    )


@router.get("/purchase/{payment_id}", response_model=PurchaseCreditsResponse)
async def purchase_status(payment_id: str, user: CurrentUser, db: DbSession):
    """Polled by the frontend after confirming a real Stripe payment
    client-side — reflects whatever the webhook has (or hasn't yet)
    recorded, never anything the client asserts."""
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if payment.status == PaymentStatus.SUCCEEDED:
        return PurchaseCreditsResponse(
            payment_id=payment.id,
            status="succeeded",
            new_balance=await credit_service.get_balance(db, user.id),
        )
    if payment.status == PaymentStatus.FAILED:
        return PurchaseCreditsResponse(payment_id=payment.id, status="failed")
    return PurchaseCreditsResponse(payment_id=payment.id, status="pending")
