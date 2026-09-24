from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import JobStatus

if TYPE_CHECKING:
    from app.models.outfit import Outfit
    from app.models.photo import UserPhoto
    from app.models.product import Product
    from app.models.user import User
    from app.models.wardrobe import WardrobeItem


class TryOnJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single virtual try-on request, run entirely out of band by a
    background worker — see app/services/queue.py + app/workers/tasks.
    Never generated synchronously inside an HTTP request.
    """

    __tablename__ = "tryon_jobs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_photo_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_photos.id", ondelete="RESTRICT"), nullable=False
    )
    # Exactly one of these three is set: a single catalog product, a
    # combined outfit, or a garment from the user's own uploaded wardrobe
    # (never shoppable — no price, no affiliate link, just their own photo
    # composited onto their fitting photo).
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=True
    )
    outfit_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("outfits.id", ondelete="RESTRICT"), nullable=True
    )
    wardrobe_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("wardrobe_items.id", ondelete="RESTRICT"), nullable=True
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=16), default=JobStatus.QUEUED, nullable=False
    )
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # what the render is doing at this moment ("Inspecting the watch"),
    # so a minute of waiting reads as work rather than a stuck spinner
    progress: Mapped[str | None] = mapped_column(String(160), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
    user_photo: Mapped["UserPhoto"] = relationship()
    product: Mapped["Product | None"] = relationship()
    outfit: Mapped["Outfit | None"] = relationship()
    wardrobe_item: Mapped["WardrobeItem | None"] = relationship()
    result: Mapped["TryOnResult | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )


class TryOnResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tryon_results"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tryon_jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # the column keeps the URL signed at upload time; reads always get a
    # freshly signed one (see storage_service.fresh_url)
    _image_url: Mapped[str] = mapped_column("image_url", String(1024), nullable=False)

    @property
    def image_url(self) -> str:
        from app.services.storage_service import fresh_url

        return fresh_url(self.storage_key, self._image_url)  # type: ignore[return-value]

    @image_url.setter
    def image_url(self, value: str) -> None:
        self._image_url = value
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # What ended up on the photo and where: one entry per item, as
    # {"name", "product_id", "slot", "drawn", "box": [x0, y0, x1, y1]} with
    # the box in fractions of the image. Written by the quality pipeline,
    # which inspects every item anyway; the result view labels each one.
    # Null for results from before this existed, or from the plain
    # (non-pipeline) path — the UI falls back to its slot list.
    placements: Mapped[list | None] = mapped_column(JSON, nullable=True)

    job: Mapped["TryOnJob"] = relationship(back_populates="result")
