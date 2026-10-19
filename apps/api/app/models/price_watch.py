"""Price alerts: a member asked to be told when a product gets cheaper or is
back in stock. One row per member and product."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PriceWatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "price_watches"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_price_watches_pair"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    # the price when the alert was set, and the lowest price the member was told about since
    start_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    told_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
