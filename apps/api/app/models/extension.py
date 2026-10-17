"""The TryOnU browser extensions (shoppers and store owners) sign in with a
token the person creates on tryonu.app/extension/connect. Only its
fingerprint is kept; the person can disconnect a browser at any time."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExtensionToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "extension_tokens"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # "shopper" | "store": which extension asked for it
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="shopper")
    # e.g. "Chrome on Windows", for the person's list of connected browsers
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
