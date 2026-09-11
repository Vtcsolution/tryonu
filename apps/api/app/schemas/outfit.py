from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import OutfitSlot
from app.schemas.common import ORMModel
from app.schemas.product import ProductOut


class OutfitItemIn(BaseModel):
    product_id: str
    slot: OutfitSlot = OutfitSlot.OTHER


class CreateOutfitRequest(BaseModel):
    name: str | None = None
    occasion: str | None = None
    items: list[OutfitItemIn]


class OutfitItemOut(ORMModel):
    id: str
    slot: OutfitSlot
    position: int
    product: ProductOut


class OutfitOut(ORMModel):
    id: str
    name: str | None
    occasion: str | None
    created_by_stylist: bool
    items: list[OutfitItemOut]
    total_price_cents: int
    created_at: datetime
