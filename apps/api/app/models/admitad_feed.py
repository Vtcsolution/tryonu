"""Products from the Admitad programmes the tryonu.app ad space is approved for.

Admitad has no live search: each programme publishes its catalogue as a feed
file. app/services/admitad_feeds.py downloads the approved feeds (daily, via
app/scripts/admitad_import.py) into this table, and the "admitad" product
source (app/retailers/admitad.py) searches it next to the live eBay and
AliExpress searches. A row is replaced whole on every import of its feed.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdmitadFeedItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admitad_feed_items"
    __table_args__ = (
        UniqueConstraint("campaign_id", "offer_id", name="uq_admitad_feed_items_offer"),
        Index("ix_admitad_feed_items_campaign_id", "campaign_id"),
    )

    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(200), nullable=False)
    offer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    old_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    # already the tracked Admitad link for our ad space: used as it is
    product_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
