"""Personalization data capture — logged now, consumed later (Phase 4:
ranking search/stylist results off a user's own saved items, try-on
history, and what they've searched/viewed). user_id is nullable so
anonymous browsing is still captured for aggregate signal (same pattern as
AffiliateClick), even before a user signs in."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class SearchHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "search_history"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    query: Mapped[str] = mapped_column(String(512), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User | None"] = relationship()


class ProductView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_views"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["User | None"] = relationship()
    product: Mapped["Product"] = relationship()
