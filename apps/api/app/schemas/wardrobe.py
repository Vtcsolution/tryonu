from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WardrobeItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    style_tags: list[str] | None = None
    notes: str | None = None


class WardrobeItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    style_tags: list[str] | None = None
    notes: str | None = None


class WardrobeItemOut(ORMModel):
    id: str
    name: str
    category: str | None
    color: str | None
    brand: str | None
    style_tags: list[str] | None
    notes: str | None
    image_url: str | None
    created_at: datetime
