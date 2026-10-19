"""Find the look: a member's photo searches, kept so they can open one again."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VisualSearch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "visual_searches"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    image_key: Mapped[str] = mapped_column(String(512), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="upload")  # upload | look | post
    summary: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # what was found: {"gender", "summary", "items": [{label, category, query, box, matches: [...]}]}
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
