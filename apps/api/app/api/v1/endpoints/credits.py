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


@router.post("/purchase", response_model=CreditTransactionOut)
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
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment requires additional confirmation on the client (see client_secret)",
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
    return entry
