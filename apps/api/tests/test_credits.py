"""The credit ledger: grant/debit/refund, insufficient-funds, and the
idempotency guarantee that prevents double-spend/double-refund on retry."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import CreditReason
from app.services import credit_service
from app.services.credit_service import InsufficientCreditsError
from tests.conftest import register_and_login


async def _new_user(client, db):
    data = await register_and_login(client)
    return data["user"]["id"]


async def test_debit_reduces_balance_and_writes_ledger_entry(client, db):
    user_id = await _new_user(client, db)
    ref = uuid.uuid4().hex

    entry = await credit_service.debit(
        db,
        user_id=user_id,
        amount=5,
        reason=CreditReason.TRYON_DEBIT,
        reference_type="test",
        reference_id=ref,
    )
    await db.commit()

    assert entry.amount == -5
    assert entry.balance_after == 95
    assert await credit_service.get_balance(db, user_id) == 95


async def test_debit_more_than_balance_raises_402(client, db):
    user_id = await _new_user(client, db)

    with pytest.raises(InsufficientCreditsError) as exc_info:
        await credit_service.debit(
            db,
            user_id=user_id,
            amount=1000,
            reason=CreditReason.TRYON_DEBIT,
            reference_type="test",
            reference_id=uuid.uuid4().hex,
        )
    assert exc_info.value.status_code == 402
    # balance must be unchanged — a failed debit is not a partial debit
    assert await credit_service.get_balance(db, user_id) == 100


async def test_debit_is_idempotent_for_the_same_reference(client, db):
    user_id = await _new_user(client, db)
    ref = uuid.uuid4().hex

    first = await credit_service.debit(
        db, user_id=user_id, amount=10, reason=CreditReason.TRYON_DEBIT,
        reference_type="tryon_job", reference_id=ref,
    )
    await db.commit()
    second = await credit_service.debit(
        db, user_id=user_id, amount=10, reason=CreditReason.TRYON_DEBIT,
        reference_type="tryon_job", reference_id=ref,
    )
    await db.commit()

    assert first.id == second.id
    # only debited once, not twice, despite calling debit() twice
    assert await credit_service.get_balance(db, user_id) == 90


async def test_refund_without_a_prior_debit_is_a_noop(client, db):
    user_id = await _new_user(client, db)

    result = await credit_service.refund(
        db,
        user_id=user_id,
        amount=5,
        reference_type="tryon_job",
        reference_id=uuid.uuid4().hex,
    )
    assert result is None
    assert await credit_service.get_balance(db, user_id) == 100


async def test_refund_after_debit_restores_balance_exactly_once(client, db):
    user_id = await _new_user(client, db)
    ref = uuid.uuid4().hex

    await credit_service.debit(
        db, user_id=user_id, amount=8, reason=CreditReason.TRYON_DEBIT,
        reference_type="tryon_job", reference_id=ref,
    )
    await db.commit()
    assert await credit_service.get_balance(db, user_id) == 92

    await credit_service.refund(db, user_id=user_id, amount=8, reference_type="tryon_job", reference_id=ref)
    await db.commit()
    assert await credit_service.get_balance(db, user_id) == 100

    # calling refund again must not double-credit
    await credit_service.refund(db, user_id=user_id, amount=8, reference_type="tryon_job", reference_id=ref)
    await db.commit()
    assert await credit_service.get_balance(db, user_id) == 100


async def test_credits_history_endpoint_reflects_the_ledger(client, db):
    data = await register_and_login(client)
    resp = await client.get("/api/v1/credits/history")
    assert resp.status_code == 200
    reasons = [row["reason"] for row in resp.json()]
    assert "signup_bonus" in reasons
