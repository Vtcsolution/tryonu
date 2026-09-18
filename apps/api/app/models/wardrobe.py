"""User-owned items — "clothes I already own" — distinct from `Product`
(the retailer catalog). A wardrobe item is never shown to other users,
never has a price/affiliate link, and is never something the AI stylist
recommends as a purchase; it's context the stylist can build real catalog
recommendations *around* (see stylist_service.py's wardrobe_item_id path).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class WardrobeItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wardrobe_items"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Free-text, not a ProductCategory FK — this is the user's own closet,
    # not the retailer catalog's taxonomy.
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    color: Mapped[str | None] = mapped_column(String(120), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    style_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # the column keeps the URL signed at upload time; reads always get a
    # freshly signed one (see storage_service.fresh_url)
    _image_url: Mapped[str | None] = mapped_column("image_url", String(1024), nullable=True)

    @property
    def image_url(self) -> str | None:
        from app.services.storage_service import fresh_url

        return fresh_url(self.storage_key, self._image_url)  # type: ignore[return-value]

    @image_url.setter
    def image_url(self, value: str | None) -> None:
        self._image_url = value

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship()
