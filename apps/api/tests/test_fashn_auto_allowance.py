"""Shoppers' try-ons run automatically within a daily FASHN limit, no approval needed."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.fashn_ledger import FashnCreditLedger, FashnLiveAuthorization
from app.services.fashn_guard import (
    SHOP_POOL,
    DbCreditGuard,
    GuardRefused,
    close_authorizations,
    guard_status,
    resume_automatic,
)


@pytest.fixture
async def fresh(db, monkeypatch):  # noqa: ANN001, ANN202
    await close_authorizations(db)
    ids = (await db.execute(select(FashnLiveAuthorization.id).where(FashnLiveAuthorization.created_by == SHOP_POOL))).scalars().all()
    if ids:
        await db.execute(delete(FashnCreditLedger).where(FashnCreditLedger.authorization_id.in_(ids)))
        await db.execute(delete(FashnLiveAuthorization).where(FashnLiveAuthorization.id.in_(ids)))
        await db.commit()
    monkeypatch.setattr(get_settings(), "SHOP_DAILY_FASHN_CREDITS", 8)
    yield db


async def _reserve(guard):  # noqa: ANN001, ANN202
    return await guard.reserve(model="tryon-max", resolution="2k", mode="quality", purpose="shop look")


async def test_a_shoppers_try_on_runs_without_any_approval_up_to_the_daily_limit(fresh):  # noqa: ANN001
    guard = DbCreditGuard(AsyncSessionLocal)
    first = await _reserve(guard)
    assert first.credits > 0
    spent = first.credits
    while spent + first.credits <= 8:
        spent += (await _reserve(guard)).credits
    with pytest.raises(GuardRefused):
        await _reserve(guard)  # today's limit is used up
    status = await guard_status(fresh)
    assert status["automatic"]["used_today"] == spent and status["automatic"]["daily_credits"] == 8


async def test_pause_stops_automatic_try_ons_and_resume_starts_them_again(fresh):  # noqa: ANN001
    guard = DbCreditGuard(AsyncSessionLocal)
    await _reserve(guard)
    await close_authorizations(fresh)  # the admin's Pause
    with pytest.raises(GuardRefused):
        await _reserve(guard)
    assert (await guard_status(fresh))["automatic"]["paused"] is True
    monkeypatch_budget = 12  # room for a third look after resuming
    await fresh.execute(
        FashnLiveAuthorization.__table__.update()
        .where(FashnLiveAuthorization.created_by == SHOP_POOL)
        .values(budget_credits=monkeypatch_budget)
    )
    await fresh.commit()
    await resume_automatic(fresh)
    assert (await _reserve(guard)).credits > 0
    assert (await guard_status(fresh))["live_generation_allowed"] is True
