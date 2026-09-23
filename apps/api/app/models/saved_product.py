"""A product a shopper actually interacted with — saved, favourited or
bought.

Only these ever enter a user's account: we never store a retailer's
catalogue, only what someone reached for. The row is a *snapshot*, not a
pointer: name, image, URLs and the price as it was at that moment are
copied in, so a look the shopper saved still shows what they saved after
the retailer edits the listing, changes the price or takes it down
altogether.

The affiliate URL is part of that snapshot, so opening a saved product
months later still credits us for the sale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SavedProductStatus

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class SavedProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saved_products"
    __table_args__ = (
        # one row per product per shopper: favouriting something twice
        # moves the existing row rather than piling up duplicates
        UniqueConstraint("user_id", "retailer_slug", "retailer_product_id", name="uq_saved_product_per_user"),
        Index("ix_saved_products_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # the catalog row, when we have one — nullable on purpose: the snapshot
    # below is what the shopper is shown, and it outlives the product row
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    retailer_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    retailer_product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    retailer_name: Mapped[str] = mapped_column(String(255), nullable=False)

    name: Mapped[str] = mapped_column(String(512), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    product_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    affiliate_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    # what it cost when they saved it — kept as-is afterwards, so a later
    # price change is visible as a change rather than quietly rewritten
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")

    status: Mapped[SavedProductStatus] = mapped_column(
        Enum(SavedProductStatus, native_enum=False, length=16),
        default=SavedProductStatus.SAVED,
        nullable=False,
    )

    user: Mapped["User"] = relationship()
    product: Mapped["Product | None"] = relationship()
