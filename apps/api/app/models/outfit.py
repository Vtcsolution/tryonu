from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import OutfitSlot

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.tryon import TryOnResult
    from app.models.user import User


class Outfit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-assembled (or stylist-recommended) set of real products,
    combined into a single virtual try-on."""

    __tablename__ = "outfits"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occasion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_stylist: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Rule-based coherence score (color/style/gender/slot-diversity) — see
    # services/outfit_compatibility.py. Computed once at creation time
    # rather than live, so it doesn't drift if a product later changes.
    compatibility_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compatibility_notes: Mapped[list | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship()
    items: Mapped[list["OutfitItem"]] = relationship(
        back_populates="outfit", cascade="all, delete-orphan", order_by="OutfitItem.position"
    )

    @property
    def total_price_cents(self) -> int:
        return sum(item.product.price_cents for item in self.items if item.product)


class OutfitItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "outfit_items"

    outfit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("outfits.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    slot: Mapped[OutfitSlot] = mapped_column(
        Enum(OutfitSlot, native_enum=False, length=16), default=OutfitSlot.OTHER, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    outfit: Mapped["Outfit"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class SavedLook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A try-on result the user chose to keep in their lookbook."""

    __tablename__ = "saved_looks"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tryon_result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tryon_results.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship()
    tryon_result: Mapped["TryOnResult"] = relationship()
