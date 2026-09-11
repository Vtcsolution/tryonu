from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AffiliateSource

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.retailer import Retailer
    from app.models.user import User


class AffiliateClick(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One "Shop Now" click — the record that lets admins measure
    click-through and (eventually) reconcile retailer commission reports."""

    __tablename__ = "affiliate_clicks"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    retailer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("retailers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source: Mapped[AffiliateSource] = mapped_column(
        Enum(AffiliateSource, native_enum=False, length=16), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    user: Mapped["User | None"] = relationship()
    product: Mapped["Product"] = relationship()
    retailer: Mapped["Retailer"] = relationship()
