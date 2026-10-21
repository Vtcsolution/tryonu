"""Company stores: businesses that sell their own products on TryOnU.

A company creates one store, an admin approves it, and it buys a plan (a
30-day pass that sets how many products it may list). Its products are then
searched next to eBay, AliExpress and Admitad, and shown FIRST to shoppers in
the store's own country. Products come from the store's dashboard (typed in,
photos uploaded) and/or a feed link (CSV/JSON) imported daily.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StorePlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A plan a store can buy: price, how many products, for how long. Admin-editable."""

    __tablename__ = "store_plans"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)  # basic | standard | premium
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    product_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    # how many of its products the store can feature (shown first when they fit a shopper's ask)
    featured_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # shopper try-ons the store pays for, included with the plan
    tryon_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # share and earn: what the person who invited a store earns when it buys this plan
    referral_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # the PayPal product + billing plan used for auto-renewing subscriptions to
    # this plan, and the "mode|price|currency|days" they were made for: a change
    # (admin edits the price, sandbox -> live) makes a fresh PayPal plan
    paypal_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paypal_plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paypal_plan_key: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Store(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stores"

    owner_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)  # ISO 3166-1 alpha-2
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # digits with the country code ("923001234567"): shoppers order and ask on WhatsApp
    whatsapp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # pending (waiting for an admin) | approved | rejected | suspended
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    plan_product_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan_featured_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # try-on credits left: each pays for one shopper's try-on of its products
    tryon_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # the current plan was given free by an admin (not paid for)
    plan_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # where it delivers: "domestic" (its own country only) | "countries" (its own
    # country and delivery_countries) | "worldwide"; shoppers elsewhere never see its products
    delivery: Mapped[str] = mapped_column(String(16), nullable=False, default="domestic")
    # ",US,GB,AE," so one LIKE finds a country in it
    delivery_countries: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    feed_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    feed_last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feed_last_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    # the plan expiry a reminder / an expired notice was emailed for (never twice)
    reminded_for_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_notice_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # auto-renew: the PayPal subscription paying for the plan every period
    subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subscription_plan_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # the last renewal payment already turned into plan time (never counted twice)
    subscription_last_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StoreProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store_products"
    __table_args__ = (
        UniqueConstraint("store_id", "external_id", name="uq_store_products_external"),
        Index("ix_store_products_store_id", "store_id"),
    )

    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    # "manual" (typed in the dashboard) | "feed" (imported from the store's feed link)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    # the store's own id for a feed product; a generated one for manual products
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    # uploaded photos are storage keys ("stores/..."), feed photos are web addresses
    images: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # where a shopper buys it: the store's own product page
    product_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="unisex")
    color: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # picked by the store to be shown first (within its plan's featured limit)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # this product's own delivery: None = as the store; "domestic" | "worldwide"
    delivery: Mapped[str | None] = mapped_column(String(16), nullable=True)


class StoreProductView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """How many times a store product was shown to shoppers on one day."""

    __tablename__ = "store_product_views"
    __table_args__ = (
        UniqueConstraint("store_product_id", "day", name="uq_store_product_views_day"),
        Index("ix_store_product_views_store_day", "store_id", "day"),
    )

    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    store_product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StoreTryOn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A shopper tried on a look with this store's product (one row per store
    product in the look). The picture is shown to the store only when shared."""

    __tablename__ = "store_tryons"
    __table_args__ = (
        Index("ix_store_tryons_store_created", "store_id", "created_at"),
        Index("ix_store_tryons_job", "tryon_job_id"),
    )

    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    store_product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("store_products.id", ondelete="SET NULL"), nullable=True
    )
    tryon_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=False)
    # the store's try-on credit paid for it (the shopper paid nothing)
    paid_by_store: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # the shopper agreed to show this store their try-on picture
    shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # the try-on failed and the store got its credit back
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shopper_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
