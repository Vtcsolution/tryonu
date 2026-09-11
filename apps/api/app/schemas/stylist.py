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


class StylistAskResponse(ORMModel):
    id: str
    summary: str
    products: list[ProductOut]
    outfit: OutfitOut | None
    created_at: datetime
