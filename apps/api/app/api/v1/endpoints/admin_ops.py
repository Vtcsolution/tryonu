"""Admin operations: refunding payments, and approving live FASHN credits
from the admin panel (the same guard and exact phrase as the command line)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import AdminUser, DbSession
from app.core.logging import logger
from app.models.admin_audit import AdminAuditLog
from app.models.enums import PaymentStatus
from app.models.subscription import Payment
from app.payments.paypal_provider import PayPalPaymentProvider
from app.payments.registry import get_payment_provider
from app.services import fashn_guard
from app.services.refund_service import reverse_payment

router = APIRouter(prefix="/admin", tags=["admin"])


class RefundIn(BaseModel):
    # "paypal": refund the money through PayPal now; "mark": it was refunded
    # outside TryOnU (PayPal dashboard, bank), only take back what it bought
    mode: str = Field(pattern=r"^(paypal|mark)$")
    reason: str | None = Field(default=None, max_length=200)


class RefundOut(BaseModel):
    status: str
    paypal_status: str | None = None
    credits_removed: int = 0
    plan_days_removed: int = 0


@router.post("/payments/{payment_id}/refund", response_model=RefundOut)
async def refund_payment(payment_id: str, payload: RefundIn, admin: AdminUser, db: DbSession):
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"This payment is {payment.status.value}, not paid.")
    paypal_status = None
    if payload.mode == "paypal":
        provider = get_payment_provider()
        one_off = payment.provider == "paypal" and payment.external_payment_id and ":" not in payment.external_payment_id
        if not isinstance(provider, PayPalPaymentProvider) or not one_off:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This payment can't be refunded from here (an auto-renew charge or another provider). "
                "Refund it in PayPal, then use 'Mark refunded'.",
            )
        try:
            paypal_status = await provider.refund_order(payment.external_payment_id, idempotency_key=payment.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("refund_failed", payment_id=payment.id, error=str(exc)[:200])
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"PayPal didn't refund: {str(exc)[:160]}") from exc
        if paypal_status == "FAILED":
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="PayPal reported the refund as failed.")
    why = payload.reason or ("refunded through PayPal" if payload.mode == "paypal" else "refunded outside TryOnU")
    taken = await reverse_payment(db, payment, why=why)
    db.add(
        AdminAuditLog(
            admin_id=admin.id, action="payment.refund", target_type="payment", target_id=payment.id,
            detail={"mode": payload.mode, "paypal_status": paypal_status, **taken},
        )
    )
    await db.commit()
    return RefundOut(
        status="refunded", paypal_status=paypal_status,
        credits_removed=taken.get("credits_removed", 0), plan_days_removed=taken.get("plan_days_removed", 0),
    )


# ------------------------------------------------------------ FASHN approval


class FashnApprovalIn(BaseModel):
    credits: int = Field(gt=0, le=fashn_guard.MAX_CREDITS_PER_AUTHORIZATION)
    hours: int = Field(gt=0, le=fashn_guard.MAX_AUTHORIZATION_HOURS)
    phrase: str = Field(min_length=1, max_length=80)


@router.get("/fashn/approval")
async def fashn_approval_status(_: AdminUser, db: DbSession) -> dict:
    status_ = await fashn_guard.guard_status(db)
    return {**status_, "max_hours": fashn_guard.MAX_AUTHORIZATION_HOURS, "phrase_example": fashn_guard.authorization_phrase(20)}


@router.post("/fashn/approval")
async def fashn_approve(payload: FashnApprovalIn, admin: AdminUser, db: DbSession) -> dict:
    """Opens an approval, exactly as `fashn_authorize --credits N --hours H --phrase ...`
    would: the phrase must name the same number of credits."""
    try:
        await fashn_guard.create_authorization(
            db, payload.credits, payload.phrase.strip(), created_by=f"admin:{admin.email}"[:120],
            note="approved in the admin panel", ttl_minutes=payload.hours * 60,
        )
    except fashn_guard.GuardRefused as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.add(AdminAuditLog(admin_id=admin.id, action="fashn.approve", target_type="fashn", target_id="approval",
                         detail={"credits": payload.credits, "hours": payload.hours}))
    await db.commit()
    return await fashn_approval_status(admin, db)


@router.post("/fashn/approval/close")
async def fashn_close(admin: AdminUser, db: DbSession) -> dict:
    closed = await fashn_guard.close_authorizations(db)
    db.add(AdminAuditLog(admin_id=admin.id, action="fashn.close", target_type="fashn", target_id="approval", detail={"closed": closed}))
    await db.commit()
    return await fashn_approval_status(admin, db)
