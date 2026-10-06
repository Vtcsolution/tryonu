"""The only gate between this application and a paid FASHN generation.

The rule: the application spends real FASHN credits only under an explicit,
operator-created authorization stored in the database, and never more than
that authorization's own budget. Each authorization states its budget in the
approval phrase itself ("AUTHORIZE 20 FASHN CREDITS"), up to
MAX_CREDITS_PER_AUTHORIZATION. A FASHN API key being present spends nothing.

How it holds:

* Every generation RESERVES its maximum cost in the database BEFORE the
  request is sent (`DbCreditGuard.reserve`). The reservation is one
  conditional UPDATE (`reserved + cost <= budget`) on the authorization row,
  committed on its own session, so it survives a crash and is race-free
  across concurrent requests and several worker processes (the row lock the
  UPDATE takes serialises them on Postgres; SQLite serialises writers).
* Nothing is refunded to the budget unless the request provably never
  reached FASHN's billing (never connected, or FASHN rejected it). A
  timeout after sending, a 5xx, a crash — all stay counted.
* No authorization, an expired one, or an exhausted budget: the request is
  refused before any network call.
* The authorization is created only by `python -m app.scripts.fashn_authorize`
  with the exact approval phrase naming its budget. It is not an environment
  variable, not a setting, and not in .env.
* A multi-product look checks `remaining()` before its first call, so a look
  the budget cannot finish is refused before anything is spent.

Reads (job status, the credit balance) spend nothing and are not gated.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import func, select, update

from app.core.logging import logger
from app.models.fashn_ledger import RELEASED, RESERVED, SUBMITTED, FashnCreditLedger, FashnLiveAuthorization

# The most one authorization may ever allow. Raising it is a deliberate code change.
MAX_CREDITS_PER_AUTHORIZATION = 100
AUTHORIZATION_TTL_MINUTES = 120
# the longest one approval may stay open (fashn_authorize --hours)
MAX_AUTHORIZATION_HOURS = 72


def authorization_phrase(credits: int) -> str:
    """The exact words an operator must type to allow `credits` of real spend."""
    return f"AUTHORIZE {credits} FASHN CREDITS"

# FASHN's documented credit cost per image for tryon-max: mode -> resolution -> credits
FASHN_CREDITS = {
    "fast": {"1k": 1, "2k": 2, "4k": 3},
    "balanced": {"1k": 2, "2k": 3, "4k": 4},
    "quality": {"1k": 3, "2k": 4, "4k": 5},
}


class GuardRefused(Exception):
    """The request must not be sent. Raised before any network call."""


def credits_per_render(resolution: str, mode: str) -> int:
    return FASHN_CREDITS[mode][resolution]


def credits_for(model: str, resolution: str | None, mode: str | None, num_images: int = 1) -> int:
    """The most FASHN can charge for this request. A model or setting with no
    known price is refused rather than guessed."""
    if model != "tryon-max":
        raise GuardRefused(f"no known FASHN price for model {model!r}; refusing to spend on it")
    try:
        return FASHN_CREDITS[mode or ""][resolution or ""] * num_images
    except KeyError as exc:
        raise GuardRefused(f"no known FASHN price for resolution={resolution!r} mode={mode!r}") from exc


class Reservation(Protocol):
    credits: int

    async def mark_submitted(self, provider_job_id: str) -> None: ...

    async def release(self, reason: str) -> None: ...


class CreditGuard(Protocol):
    async def reserve(
        self, *, model: str, resolution: str | None, mode: str | None, purpose: str
    ) -> Reservation: ...


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _active_authorization(db):  # noqa: ANN001, ANN202
    now = datetime.now(timezone.utc)
    rows = await db.execute(
        select(FashnLiveAuthorization)
        .where(FashnLiveAuthorization.status == "active")
        .order_by(FashnLiveAuthorization.created_at.desc())
    )
    return next((a for a in rows.scalars() if _aware(a.expires_at) is None or _aware(a.expires_at) > now), None)


async def _spent(db) -> int:  # noqa: ANN001
    """Every credit ever set aside and not provably given back."""
    total = await db.scalar(
        select(func.coalesce(func.sum(FashnCreditLedger.credits), 0)).where(FashnCreditLedger.state != RELEASED)
    )
    return int(total or 0)


@dataclass
class _DbReservation:
    entry_id: str
    authorization_id: str
    credits: int
    _factory: Callable

    async def mark_submitted(self, provider_job_id: str) -> None:
        try:
            async with self._factory() as db:
                await db.execute(
                    update(FashnCreditLedger)
                    .where(FashnCreditLedger.id == self.entry_id, FashnCreditLedger.state == RESERVED)
                    .values(state=SUBMITTED, provider_job_id=provider_job_id)
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001 — the entry stays counted as reserved; never lose a paid job over this
            logger.error("fashn_ledger_mark_submitted_failed", entry=self.entry_id, error=str(exc)[:200])

    async def release(self, reason: str) -> None:
        try:
            async with self._factory() as db:
                changed = await db.execute(
                    update(FashnCreditLedger)
                    .where(FashnCreditLedger.id == self.entry_id, FashnCreditLedger.state == RESERVED)
                    .values(state=RELEASED, release_reason=reason[:255])
                )
                if changed.rowcount == 1:
                    await db.execute(
                        update(FashnLiveAuthorization)
                        .where(
                            FashnLiveAuthorization.id == self.authorization_id,
                            FashnLiveAuthorization.reserved_credits >= self.credits,
                        )
                        .values(reserved_credits=FashnLiveAuthorization.reserved_credits - self.credits)
                    )
                await db.commit()
        except Exception as exc:  # noqa: BLE001 — failing to give credits back only makes the cap stricter
            logger.error("fashn_ledger_release_failed", entry=self.entry_id, error=str(exc)[:200])


class DbCreditGuard:
    """The production guard: reservations live in the application database."""

    def __init__(self, session_factory: Callable | None = None) -> None:
        self._factory = session_factory

    def _sessions(self):  # noqa: ANN202
        if self._factory is None:
            from app.db.session import AsyncSessionLocal

            return AsyncSessionLocal
        return self._factory

    async def remaining(self) -> int:
        """Credits the open authorization still allows; 0 when there is none."""
        async with self._sessions()() as db:
            authorization = await _active_authorization(db)
            if authorization is None:
                return 0
            return max(0, authorization.budget_credits - authorization.reserved_credits)

    async def reserve(
        self, *, model: str, resolution: str | None, mode: str | None, purpose: str
    ) -> _DbReservation:
        cost = credits_for(model, resolution, mode)
        factory = self._sessions()
        async with factory() as db:
            authorization = await _active_authorization(db)
            if authorization is None:
                raise GuardRefused(
                    "Live FASHN generation is not authorized. Nothing was sent. "
                    "An operator must run `python -m app.scripts.fashn_authorize` first."
                )

            # The one atomic step: succeeds only while the budget still has room.
            claimed = await db.execute(
                update(FashnLiveAuthorization)
                .where(
                    FashnLiveAuthorization.id == authorization.id,
                    FashnLiveAuthorization.status == "active",
                    FashnLiveAuthorization.reserved_credits + cost <= FashnLiveAuthorization.budget_credits,
                )
                .values(reserved_credits=FashnLiveAuthorization.reserved_credits + cost)
            )
            if claimed.rowcount != 1:
                await db.rollback()
                raise GuardRefused(
                    f"The FASHN credit budget is exhausted (this request needs {cost}). Nothing was sent."
                )
            entry = FashnCreditLedger(
                authorization_id=authorization.id,
                state=RESERVED,
                credits=cost,
                model=model,
                resolution=resolution,
                generation_mode=mode,
                purpose=purpose[:160],
            )
            db.add(entry)
            await db.commit()
            return _DbReservation(entry.id, authorization.id, cost, factory)


async def create_authorization(
    db,  # noqa: ANN001
    credits: int,
    phrase: str,
    *,
    created_by: str = "operator",
    note: str | None = None,
    ttl_minutes: int = AUTHORIZATION_TTL_MINUTES,
) -> FashnLiveAuthorization:
    """Opens a one-time authorization for exactly `credits`. Refused unless the
    phrase names that same amount, when the amount is out of range, or while
    another authorization still has budget to spend."""
    if not 1 <= ttl_minutes <= MAX_AUTHORIZATION_HOURS * 60:
        raise GuardRefused(f"An authorization can stay open between 1 minute and {MAX_AUTHORIZATION_HOURS} hours. Nothing authorized.")
    if not 1 <= credits <= MAX_CREDITS_PER_AUTHORIZATION:
        raise GuardRefused(
            f"An authorization must be between 1 and {MAX_CREDITS_PER_AUTHORIZATION} credits. Nothing authorized."
        )
    if phrase != authorization_phrase(credits):
        raise GuardRefused(
            f'The approval phrase does not match. Type exactly: "{authorization_phrase(credits)}". '
            "No authorization was created."
        )
    now = datetime.now(timezone.utc)
    open_rows = await db.execute(select(FashnLiveAuthorization).where(FashnLiveAuthorization.status == "active"))
    for existing in open_rows.scalars():
        expired = _aware(existing.expires_at) is not None and _aware(existing.expires_at) <= now
        if not expired and existing.reserved_credits < existing.budget_credits:
            raise GuardRefused(f"Authorization {existing.id} is still open with budget left. Close it first.")
    authorization = FashnLiveAuthorization(
        budget_credits=credits,
        reserved_credits=0,
        status="active",
        expires_at=now + timedelta(minutes=ttl_minutes),
        created_by=created_by[:120],
        note=note,
    )
    db.add(authorization)
    await db.commit()
    return authorization


async def close_authorizations(db) -> int:  # noqa: ANN001
    result = await db.execute(
        update(FashnLiveAuthorization).where(FashnLiveAuthorization.status == "active").values(status="closed")
    )
    await db.commit()
    return int(result.rowcount or 0)


async def guard_status(db) -> dict:  # noqa: ANN001
    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(select(FashnLiveAuthorization).where(FashnLiveAuthorization.status == "active"))
    ).scalars().all()
    live = [a for a in rows if _aware(a.expires_at) is None or _aware(a.expires_at) > now]
    return {
        "live_generation_allowed": bool(live) and any(a.reserved_credits < a.budget_credits for a in live),
        "max_credits_per_authorization": MAX_CREDITS_PER_AUTHORIZATION,
        "counted_as_spent_credits_all_time": await _spent(db),
        "open_authorizations": [
            {"id": a.id, "budget": a.budget_credits, "reserved": a.reserved_credits, "expires_at": str(a.expires_at)}
            for a in live
        ],
    }
