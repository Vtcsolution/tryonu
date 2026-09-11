from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CreditReason

if TYPE_CHECKING:
    from app.models.user import User


class CreditTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only ledger — the source of truth for every credit's origin.
    `User.credits_balance` is a cache written in the same DB transaction."""

    __tablename__ = "credit_transactions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # signed: + credit, - debit
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[CreditReason] = mapped_column(
        Enum(CreditReason, native_enum=False, length=32), nullable=False
    )
    # Loosely-typed pointer to whatever caused this entry (a try-on job,
    # a payment, an admin action) — avoids one FK per reason type.
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship(back_populates="credit_transactions")


class CreditPackage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Purchasable credit bundle (one-off top-up)."""

    __tablename__ = "credit_packages"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="usd", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
