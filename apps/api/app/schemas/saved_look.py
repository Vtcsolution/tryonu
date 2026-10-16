from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel
from app.schemas.product import ProductOut


class SavedLookItemOut(BaseModel):
    id: str
    name: str
    price_cents: int
    currency: str
    image_url: str | None
    shop: str | None
    on_photo: bool | None = None


class SavedLookOut(ORMModel):
    id: str
    title: str | None
    image_url: str | None
    product: ProductOut | None
    created_at: datetime
    # the try-on behind it: what Share shares
    tryon_job_id: str | None = None
    # every product in the look (an outfit's too, all rounds)
    items: list[SavedLookItemOut] = []
    total_cents: int | None = None
    currency: str | None = None
