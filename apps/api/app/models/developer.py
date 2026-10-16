"""The TryOnU Developer API: other businesses add TryOnU's virtual try-on to
their own sites and apps, paying per try-on with prepaid credits.

Kept apart from shoppers' credits and company stores' try-on credits: a
developer account has its own balance, keys, packs and usage.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeveloperAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One per user who signs up for the Developer API."""

    __tablename__ = "developer_accounts"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(120), nullable=False)
    website: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # prepaid try-ons left: 1 credit = 1 try-on
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # active | suspended (an admin can stop an account)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class DeveloperApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A key a developer calls the API with. Only a SHA-256 fingerprint is
    kept: the full key is shown once, when it is made."""

    __tablename__ = "developer_api_keys"
    __table_args__ = (Index("ix_developer_api_keys_account", "account_id"),)

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("developer_accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # secret (servers) | public (websites, limited to allowed_domains)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="secret")
    # the start of the key, to recognise it in the list ("tou_sk_ab12cd")
    prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    allowed_domains: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeveloperCreditPack(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A pack of try-ons a developer can buy. Admin-editable."""

    __tablename__ = "developer_credit_packs"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)  # starter | growth | scale
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    tryons: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DeveloperTryOn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One try-on made through the API, and the credit it used."""

    __tablename__ = "developer_tryons"
    __table_args__ = (
        Index("ix_developer_tryons_account_created", "account_id", "created_at"),
        Index("ix_developer_tryons_job", "tryon_job_id"),
    )

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("developer_accounts.id", ondelete="CASCADE"), nullable=False
    )
    api_key_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("developer_api_keys.id", ondelete="SET NULL"), nullable=True
    )
    tryon_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # the try-on failed and the credit went back
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # the developer's own reference (an order or product id), returned as given
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
