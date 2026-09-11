from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Gender

if TYPE_CHECKING:
    from app.models.user import User


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Feeds the AI stylist: sizes, colors, styles, budget, occasions."""

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, native_enum=False, length=16), nullable=True
    )
    preferred_sizes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    preferred_colors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    preferred_styles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    preferred_brands: Mapped[list | None] = mapped_column(JSON, nullable=True)
    favorite_retailers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    budget_min_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_max_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="preference")
