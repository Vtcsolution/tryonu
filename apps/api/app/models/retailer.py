from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Retailer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A connected marketplace (Amazon, eBay, Flipkart, Daraz, ...).

    `slug` is the key application code should ever hard-code (if at all —
    prefer looking retailers up by slug from config/DB, see
    app/retailers/registry.py) so a new retailer is pure data + one adapter
    class, never a core-app change.
    """

    __tablename__ = "retailers"

    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    affiliate_network: Mapped[str | None] = mapped_column(String(120), nullable=True)
    base_commission_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_categories"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True
    )
