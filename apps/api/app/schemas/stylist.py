from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel
from app.schemas.outfit import OutfitOut
from app.schemas.product import LiveProductOut, ProductOut


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
    # Real alternatives at other price points for each recommended product
    # (single-product or outfit item), keyed by that product's id — fetched
    # live alongside the pick itself, never a separate/extra API call, and
    # never invented. Empty for /history replays (only available right
    # when the recommendation was made).
    alternatives: dict[str, list[LiveProductOut]] = {}
    created_at: datetime
