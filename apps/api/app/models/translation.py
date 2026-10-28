"""A piece of the website's text in another language, made once by the AI
and kept: the next visitor gets it from here (see translate_service)."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Translation(Base):
    __tablename__ = "translations"

    lang: Mapped[str] = mapped_column(String(8), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 of the English text
    source: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
