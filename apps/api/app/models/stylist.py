from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class StylistRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One turn with the AI fashion stylist: the free-text ask, the
    structured constraints extracted from it, and the real product ids it
    recommended (never invented products)."""

    __tablename__ = "stylist_requests"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    occasion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget_min_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_max_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    style: Mapped[str | None] = mapped_column(String(255), nullable=True)

    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_product_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recommended_outfit_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("outfits.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship()
