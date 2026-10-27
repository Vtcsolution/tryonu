"""Ready looks: complete outfits the TryOnU team put on a model with a real
try-on, published on tryonu.app/looks for shoppers to try on themselves.

A team member makes the try-on with their own credits, then publishes it. The
look keeps its own copy of the picture (and the "outfit receipt" picture made
from it for the page and for social media), so it stays up even if the
try-on is later deleted.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReadyLook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ready_looks"

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    # women | men | kids
    audience: Mapped[str] = mapped_column(String(12), nullable=False, default="women", index=True)
    # a short tag shown on the card, e.g. "Winter"
    season: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    tryon_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tryon_jobs.id", ondelete="SET NULL"), nullable=True)
    # the model wearing the outfit, and the outfit-receipt picture made from it
    image_key: Mapped[str] = mapped_column(String(512), nullable=False)
    card_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # bumped whenever the pictures change, so browsers fetch the new ones
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    # higher first on the page
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    items: Mapped[list["ReadyLookItem"]] = relationship(
        back_populates="look", cascade="all, delete-orphan", order_by="ReadyLookItem.position"
    )


class ReadyLookItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ready_look_items"

    look_id: Mapped[str] = mapped_column(String(36), ForeignKey("ready_looks.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # where the piece is on the picture (fractions x0, y0, x1, y1), when the try-on said
    box: Mapped[str | None] = mapped_column(String(64), nullable=True)

    look: Mapped[ReadyLook] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # noqa: F821
