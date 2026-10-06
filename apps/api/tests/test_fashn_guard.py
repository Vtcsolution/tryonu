"""The database credit guard, against the real test database. No network."""

from __future__ import annotations

import pytest

from app.db.session import AsyncSessionLocal
from app.services.fashn_guard import (
    MAX_CREDITS_PER_AUTHORIZATION,
    DbCreditGuard,
    GuardRefused,
    authorization_phrase,
    close_authorizations,
    create_authorization,
    guard_status,
)


@pytest.fixture
async def clean(db):
    await close_authorizations(db)
    yield db
    await close_authorizations(db)


async def _reserve(guard: DbCreditGuard):
    return await guard.reserve(model="tryon-max", resolution="1k", mode="balanced", purpose="test")


async def test_the_phrase_must_name_the_same_amount(clean):
    assert authorization_phrase(20) == "AUTHORIZE 20 FASHN CREDITS"
    with pytest.raises(GuardRefused, match="does not match"):
        await create_authorization(clean, 20, "AUTHORIZE 2 FASHN CREDITS")
    with pytest.raises(GuardRefused, match="does not match"):
        await create_authorization(clean, 20, "RUN THE 2-CREDIT FASHN TEST")


async def test_an_amount_out_of_range_is_refused(clean):
    too_many = MAX_CREDITS_PER_AUTHORIZATION + 1
    with pytest.raises(GuardRefused, match="between 1 and"):
        await create_authorization(clean, too_many, authorization_phrase(too_many))
    with pytest.raises(GuardRefused, match="between 1 and"):
        await create_authorization(clean, 0, authorization_phrase(0))


async def test_nothing_can_be_reserved_without_an_authorization(clean):
    guard = DbCreditGuard(AsyncSessionLocal)
    assert await guard.remaining() == 0
    with pytest.raises(GuardRefused, match="not authorized"):
        await _reserve(guard)


async def test_reservations_stay_within_the_approved_budget(clean):
    await create_authorization(clean, 5, authorization_phrase(5))
    guard = DbCreditGuard(AsyncSessionLocal)
    assert await guard.remaining() == 5

    first = await _reserve(guard)  # 1k balanced = 2
    second = await _reserve(guard)
    assert (first.credits, second.credits) == (2, 2)
    assert await guard.remaining() == 1
    with pytest.raises(GuardRefused, match="exhausted"):
        await _reserve(guard)


async def test_only_a_provably_unbilled_request_gives_credits_back(clean):
    spent_before = (await guard_status(clean))["counted_as_spent_credits_all_time"]
    await create_authorization(clean, 4, authorization_phrase(4))
    guard = DbCreditGuard(AsyncSessionLocal)
    sent = await _reserve(guard)
    await sent.mark_submitted("job_1")
    never_connected = await _reserve(guard)
    await never_connected.release("never connected")

    assert await guard.remaining() == 2
    status = await guard_status(clean)
    assert status["counted_as_spent_credits_all_time"] == spent_before + 2  # the released one is not counted


async def test_a_second_authorization_is_refused_while_one_has_budget(clean):
    await create_authorization(clean, 4, authorization_phrase(4))
    with pytest.raises(GuardRefused, match="still open"):
        await create_authorization(clean, 2, authorization_phrase(2))


async def test_one_approval_can_stay_open_for_a_day_but_not_longer_than_72_hours(clean):
    from datetime import datetime, timedelta, timezone

    day = await create_authorization(clean, 20, authorization_phrase(20), ttl_minutes=24 * 60)
    left = day.expires_at.replace(tzinfo=day.expires_at.tzinfo or timezone.utc) - datetime.now(timezone.utc)
    assert timedelta(hours=23, minutes=59) < left <= timedelta(hours=24)
    await close_authorizations(clean)
    with pytest.raises(GuardRefused, match="72 hours"):
        await create_authorization(clean, 20, authorization_phrase(20), ttl_minutes=73 * 60)
