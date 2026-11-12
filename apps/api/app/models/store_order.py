"""An order a customer placed on a store's own TryOnU page (tryonu.app/<store>).
TryOnU takes no payment: the store gets the order by email (and the customer
sends it on WhatsApp), then confirms, delivers and is paid as they agree."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StoreOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store_orders"
    __table_args__ = (Index("ix_store_orders_store_created", "store_id", "created_at"),)

    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)  # TU-7K3F9Q
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{product_id, name, price_cents, qty, image}] as they were when ordered
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    # new | confirmed | shipped | delivered | cancelled
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="new", index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
