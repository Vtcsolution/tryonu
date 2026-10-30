"""A shopper's "this try-on came out wrong": an admin looks at the picture and
refunds the credits or dismisses it (Admin → Try-ons)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TryOnReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tryon_reports"

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("tryon_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # wrong_product | merged | extra_item | not_me | bad_quality | other
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # open | refunded | dismissed
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open", index=True)
    credits_refunded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    job: Mapped["TryOnJob"] = relationship()  # noqa: F821
    user: Mapped["User"] = relationship()  # noqa: F821
