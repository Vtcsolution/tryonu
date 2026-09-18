from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PhotoKind

if TYPE_CHECKING:
    from app.models.user import User


class UserPhoto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One photo in a user's fitting profile. FRONT and FULL_BODY are
    required before a try-on can run; the rest are optional extras that
    improve result quality."""

    __tablename__ = "user_photos"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[PhotoKind] = mapped_column(Enum(PhotoKind, native_enum=False, length=16), nullable=False)

    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # the column keeps the URL signed at upload time; reads always get a
    # freshly signed one (see storage_service.fresh_url)
    _url: Mapped[str] = mapped_column("url", String(1024), nullable=False)

    @property
    def url(self) -> str:
        from app.services.storage_service import fresh_url

        return fresh_url(self.storage_key, self._url)  # type: ignore[return-value]

    @url.setter
    def url(self, value: str) -> None:
        self._url = value
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="photos")  # noqa: F821
