"""Share and earn: a friend who joined from someone's link (a shared look or
their invite link). The sharer earns credits once, when that friend first
buys credits (never for the sign-up alone, so fake accounts earn nothing)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Referral(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "referrals"

    referrer_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # one referrer per person, ever
    referred_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # "look:<token>" or "link"
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ReferralCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A person's own invite code: tryonu.app/?ref=<code>."""

    __tablename__ = "referral_codes"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
