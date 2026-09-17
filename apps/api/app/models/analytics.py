from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PageView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One page view on the public site, for the admin analytics panel.

    Deliberately stores no IP address: the request IP is only used to look
    up `country` at write time. `visitor_id`/`session_id` are random ids the
    browser generates, not derived from anything identifying."""

    __tablename__ = "page_views"
    __table_args__ = (Index("ix_page_views_created_at", "created_at"),)

    visitor_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    path: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    referrer_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), index=True, nullable=True)  # ISO 3166-1 alpha-2
    device: Mapped[str] = mapped_column(String(16), nullable=False)  # desktop | mobile | tablet
    browser: Mapped[str] = mapped_column(String(32), nullable=False)
    os: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
