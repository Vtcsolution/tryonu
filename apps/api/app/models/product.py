from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import Vector
from app.models.enums import Availability, Gender

if TYPE_CHECKING:
    from app.models.retailer import ProductCategory, Retailer


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A normalized product, regardless of which retailer it came from.

    Ingestion adapters (app/retailers/*) each speak their retailer's native
    API/feed format and map into exactly this shape — the rest of the app
    (search, stylist, try-on, affiliate tracking) only ever sees `Product`.
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("retailer_id", "retailer_product_id", name="uq_retailer_product"),
        Index("ix_products_price", "price_cents"),
        Index("ix_products_gender_category", "gender", "category_id"),
    )

    retailer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("retailers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True
    )
    # The retailer's own identifier (ASIN, eBay item id, SKU, ...) — the
    # ingestion upsert key alongside retailer_id.
    retailer_product_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # For aggregator networks (Rakuten, CJ) where the network isn't the
    # seller — the actual merchant/advertiser, distinct from `brand`.
    # Nullable and unused by direct retailers (eBay, Amazon, ...).
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gender: Mapped[Gender] = mapped_column(
        Enum(Gender, native_enum=False, length=16), default=Gender.UNISEX, nullable=False
    )
    color: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # MVP: sizes as a flat list on the product ("S","M","L",...). A real
    # size/stock matrix belongs in a ProductVariant table — natural next
    # step, deliberately out of scope for the MVP schema.
    sizes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    style_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="usd", nullable=False)

    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    affiliate_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    availability: Mapped[Availability] = mapped_column(
        Enum(Availability, native_enum=False, length=16),
        default=Availability.IN_STOCK,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Text embedding of "name brand category color description" for
    # semantic search + the AI stylist's nearest-neighbour matching.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    retailer: Mapped["Retailer"] = relationship()
    category: Mapped["ProductCategory | None"] = relationship()
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.position"
    )

    @property
    def primary_image_url(self) -> str | None:
        return self.images[0].url if self.images else None


class ProductImage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "product_images"

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="images")
