from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel
from app.schemas.outfit import OutfitOut
from app.schemas.product import ProductOut


class StylistAskRequest(BaseModel):
    prompt: str
    occasion: str | None = None
    budget_min_cents: int | None = None
    budget_max_cents: int | None = None
    style: str | None = None
    max_items: int = 6
    # "Build an outfit around my black trousers" — a wardrobe item the
    # stylist should treat as a fixed anchor when picking real catalog
    # products to complement it. Never recommended itself (it's not a
    # catalog Product); ownership is checked in stylist_service.py.
    wardrobe_item_id: str | None = None


class StylistAskResponse(ORMModel):
    id: str
    prompt: str
    summary: str
    products: list[ProductOut]
    outfit: OutfitOut | None
    created_at: datetime
