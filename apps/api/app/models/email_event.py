"""An automatic email a member was sent (welcome, "your first outfit is
waiting", "your look is ready"), so each goes to each person only once."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserEmailEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_email_events"
    __table_args__ = (UniqueConstraint("user_id", "kind", "ref", name="uq_user_email_event"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # welcome | first_look | look_ready
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    ref: Mapped[str] = mapped_column(String(36), nullable=False, default="")  # the try-on, for look_ready
