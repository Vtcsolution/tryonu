from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# ledger entry states
RESERVED = "reserved"  # the cost is set aside; a request may or may not have been sent
SUBMITTED = "submitted"  # FASHN accepted a job (its id is recorded)
RELEASED = "released"  # provably never billed (never connected, or FASHN rejected the request)


class FashnLiveAuthorization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An explicit, operator-created permission to spend a fixed number of
    REAL FASHN credits. Without an active row here the application cannot
    contact FASHN to generate anything, whatever keys are configured.

    `reserved_credits` is the running total of every non-released ledger
    entry. It is only ever changed by a single conditional UPDATE
    (`reserved + cost <= budget`), which is what makes the cap hold across
    concurrent requests and multiple worker processes."""

    __tablename__ = "fashn_live_authorizations"
    __table_args__ = (
        CheckConstraint("reserved_credits >= 0", name="ck_fashn_auth_reserved_nonneg"),
        CheckConstraint("reserved_credits <= budget_credits", name="ck_fashn_auth_within_budget"),
    )

    budget_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # "active" or "closed". A closed authorization never reopens.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="operator")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class FashnCreditLedger(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One attempted FASHN generation, written BEFORE the request is sent.

    Everything except `released` counts as spent: a crash, a timeout after
    sending, or a 5xx leaves the entry counted, so the cap can only err on
    the side of refusing."""

    __tablename__ = "fashn_credit_ledger"
    __table_args__ = (Index("ix_fashn_ledger_auth_state", "authorization_id", "state"),)

    authorization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fashn_live_authorizations.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=RESERVED)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(8), nullable=True)
    generation_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # who asked: "direct:<job id>", "legacy", "script:<name>" …
    purpose: Mapped[str] = mapped_column(String(160), nullable=False, default="unspecified")
    provider_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    release_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
