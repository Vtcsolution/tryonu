"""A try-on result its owner chose to share: a public link anyone can open.

Only ever made when the owner presses Share (the picture shows their own face
and body), and the owner can stop sharing at any time: the link then stops
working, the picture included.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SharedLook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shared_looks"

    # the unguessable part of the link: tryonu.app/look/<token>
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tryon_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tryon_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
