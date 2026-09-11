"""The credit ledger — the only code allowed to change a balance.

Every mutation is: lock the user row -> compute new balance -> insert an
append-only CreditTransaction -> write the cached balance back, all inside
one DB transaction. The frontend never sends a credit amount; it only ever
reads `CreditBalanceOut` back from the API. Debits are idempotent per
(reference_type, reference_id, reason) so a retried request or a duplicated
worker message can never double-charge or double-refund.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditTransaction
from app.models.enums import CreditReason
from app.models.user import User


class InsufficientCreditsError(HTTPException):
    def __init__(self, required: int, available: int) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits: need {required}, have {available}",
        )


async def _lock_user(db: AsyncSession, user_id: str) -> User:
    dialect = db.bind.dialect.name if db.bind is not None else ""
    stmt = select(User).where(User.id == user_id)
    if dialect == "postgresql":
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    user = result.scalar_one()
    return user


async def _existing_entry(
    db: AsyncSession, reference_type: str, reference_id: str, reason: CreditReason
) -> CreditTransaction | None:
    result = await db.execute(
        select(CreditTransaction).where(
            CreditTransaction.reference_type == reference_type,
            CreditTransaction.reference_id == reference_id,
            CreditTransaction.reason == reason,
        )
    )
    return result.scalar_one_or_none()


async def grant(
    db: AsyncSession,
    *,
    user_id: str,
    amount: int,
    reason: CreditReason,
    reference_type: str | None = None,
    reference_id: str | None = None,
    note: str | None = None,
    idempotent: bool = True,
) -> CreditTransaction:
    if amount <= 0:
        raise ValueError("grant() amount must be positive")

    if idempotent and reference_type and reference_id:
        existing = await _existing_entry(db, reference_type, reference_id, reason)
        if existing:
            return existing

    user = await _lock_user(db, user_id)
    user.credits_balance += amount
    entry = CreditTransaction(
        user_id=user.id,
        amount=amount,
        balance_after=user.credits_balance,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
    )
    db.add(entry)
    await db.flush()
    return entry


async def debit(
    db: AsyncSession,
    *,
    user_id: str,
    amount: int,
    reason: CreditReason,
    reference_type: str | None = None,
    reference_id: str | None = None,
    note: str | None = None,
) -> CreditTransaction:
    if amount <= 0:
        raise ValueError("debit() amount must be positive")

    if reference_type and reference_id:
        existing = await _existing_entry(db, reference_type, reference_id, reason)
        if existing:
            return existing

    user = await _lock_user(db, user_id)
    if user.credits_balance < amount:
        raise InsufficientCreditsError(required=amount, available=user.credits_balance)

    user.credits_balance -= amount
    entry = CreditTransaction(
        user_id=user.id,
        amount=-amount,
        balance_after=user.credits_balance,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
    )
    db.add(entry)
    await db.flush()
    return entry


async def refund(
    db: AsyncSession,
    *,
    user_id: str,
    amount: int,
    reference_type: str,
    reference_id: str,
    note: str | None = None,
) -> CreditTransaction | None:
    """Refunds a failed job's debit exactly once — safe to call repeatedly
    (e.g. from a retry path) because of the idempotency check in grant()."""
    # Never refund something that was never debited.
    debited = await _existing_entry(db, reference_type, reference_id, CreditReason.TRYON_DEBIT)
    if debited is None:
        return None
    return await grant(
        db,
        user_id=user_id,
        amount=amount,
        reason=CreditReason.TRYON_REFUND,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note or "Automatic refund — AI job failed",
    )


async def get_balance(db: AsyncSession, user_id: str) -> int:
    user = await db.get(User, user_id)
    return user.credits_balance if user else 0
