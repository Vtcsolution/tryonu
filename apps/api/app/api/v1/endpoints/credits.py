from __future__ import annotations

from app.payments.base import failure_detail

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models.credit import CreditPackage
from app.models.enums import CreditReason, PaymentStatus
from app.models.subscription import Payment
from app.core.logging import logger
from app.payments.base import PaymentsUnavailableError
from app.payments.registry import GATEWAY_LABELS, checkout_provider, enabled_gateways, get_payment_provider
from app.schemas.credit import (
    CreditBalanceOut,
    CreditPackageOut,
    CreditPricingOut,
    CreditTransactionOut,
    PurchaseCreditsRequest,
    PurchaseCreditsResponse,
)
from app.services import credit_service
from app.services.payment_settlement import settle

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


@router.get("/pricing", response_model=CreditPricingOut)
async def pricing():
    """Credits per try-on, for the shop and try-on pages (public: no account needed)."""
    s = get_settings()
    return CreditPricingOut(tryon_cost=s.TRYON_CREDIT_COST, outfit_tryon_cost=s.OUTFIT_TRYON_CREDIT_COST)


async def has_bought_credits(db: DbSession, user_id: str) -> bool:
    """Whether this member already paid for credits once (first-purchase offers end then)."""
    return (
        await db.scalar(
            select(Payment.id)
            .where(Payment.user_id == user_id, Payment.credit_package_id.is_not(None), Payment.status == PaymentStatus.SUCCEEDED)
            .limit(1)
        )
    ) is not None


@router.get("/packages", response_model=list[CreditPackageOut])
async def packages(db: DbSession, user: OptionalUser):
    """Credit packs on sale, the first-purchase offer first. A member who has
    bought before no longer sees the offer; visitors without an account do."""
    rows = list((await db.execute(select(CreditPackage).where(CreditPackage.is_active.is_(True)))).scalars().all())
    if user is not None and await has_bought_credits(db, user.id):
        rows = [p for p in rows if not p.new_members_only]
    rows.sort(key=lambda p: (not p.new_members_only, p.price_cents))
    return rows


@router.get("/checkout-config")
async def checkout_config():
    """Which checkout the website opens. Paddle's client-side token is public by design."""
    from app.core.config import get_settings

    provider = get_payment_provider()
    settings = get_settings()
    on = enabled_gateways()
    paddle = None
    if "paddle" in on:
        live = settings.PADDLE_MODE == "live"
        token = settings.PADDLE_CLIENT_TOKEN if live else settings.PADDLE_SANDBOX_CLIENT_TOKEN
        paddle = {"token": token, "environment": "production" if live else "sandbox"} if token else None
    gateways = [{"id": g, "label": GATEWAY_LABELS[g]} for g in on]
    return {"provider": provider.name, "gateways": gateways, "paddle": paddle}


@router.post("/purchase", response_model=PurchaseCreditsResponse)
async def purchase(payload: PurchaseCreditsRequest, user: CurrentUser, db: DbSession, gateway: str | None = None):
    admin_view = user.is_admin  # read now: after a rollback the user row can't be read lazily
    package = await db.get(CreditPackage, payload.credit_package_id)
    if package is None or not package.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit package not found")
    if package.new_members_only and await has_bought_credits(db, user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This offer is for your first purchase only. Please choose another pack.",
        )

    provider = checkout_provider(gateway, get_payment_provider)
    # the payment row first, so a redirect provider (PayPal) can send the
    # shopper back to a page that knows which payment to confirm
    payment = Payment(
        user_id=user.id,
        amount_cents=package.price_cents,
        currency=package.currency,
        status=PaymentStatus.PENDING,
        provider=provider.name,
        credit_package_id=package.id,
    )
    db.add(payment)
    await db.flush()
    try:
        checkout = await provider.create_checkout(
            amount_cents=package.price_cents,
            currency=package.currency,
            user_id=user.id,
            metadata={
                "credit_package_id": package.id,
                "credits": package.credits,
                "payment_id": payment.id,
                "description": f"{package.credits} TryOnU credits ({package.name})",
            },
        )
    except PaymentsUnavailableError as exc:
        await db.rollback()
        logger.warning("payments_unavailable", provider=provider.name, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not available right now. Nothing was charged; please try again later.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — the processor refused or was unreachable
        await db.rollback()
        logger.warning("payment_checkout_failed", provider=provider.name, error=str(exc)[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=failure_detail("We couldn't start the payment. Nothing was charged; please try again.", exc, is_admin=admin_view),
        ) from exc
    payment.external_payment_id = checkout.external_payment_id
    if checkout.status == "succeeded":
        payment.status = PaymentStatus.SUCCEEDED
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


@router.post("/purchase/{payment_id}/capture", response_model=PurchaseCreditsResponse)
async def capture_purchase(payment_id: str, user: CurrentUser, db: DbSession):
    """The shopper is back from PayPal: take the money and grant the credits.

    PayPal itself is asked what was captured; nothing the browser says counts.
    Credits are granted only for a COMPLETED capture of exactly this payment's
    amount and currency, and only once: a reload or a second click finds the
    payment already succeeded and returns it as it is."""
    payment = (
        await db.execute(select(Payment).where(Payment.id == payment_id).with_for_update())
    ).scalar_one_or_none()
    if payment is None or payment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.status == PaymentStatus.SUCCEEDED:
        return PurchaseCreditsResponse(
            payment_id=payment.id, status="succeeded", new_balance=await credit_service.get_balance(db, user.id)
        )
    if payment.status != PaymentStatus.PENDING or not payment.external_payment_id:
        return PurchaseCreditsResponse(payment_id=payment.id, status="failed")

    return await settle(db, payment)


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
