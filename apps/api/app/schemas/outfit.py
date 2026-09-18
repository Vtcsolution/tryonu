from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, computed_field

from app.models.enums import OutfitSlot
from app.schemas.common import ORMModel
from app.schemas.product import ProductOut
from app.services.outfit_slots import render_plan


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


class CompatibilityPreviewRequest(BaseModel):
    items: list[OutfitItemIn]


class CompatibilityPreviewResponse(BaseModel):
    overall: int
    color: int
    style: int
    notes: list[str]


class OutfitOut(ORMModel):
    id: str
    name: str | None
    occasion: str | None
    created_by_stylist: bool
    items: list[OutfitItemOut]
    total_price_cents: int
    compatibility_score: int | None
    compatibility_notes: list[str] | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rendered_item_ids(self) -> list[str]:
        """Items the configured try-on model will actually draw on the photo
        — the rest are shown alongside as matched products. Same plan the
        try-on worker uses, so the "on photo" labels never over-promise."""
        from app.ai.providers.registry import get_tryon_provider

        provider = get_tryon_provider()
        plan = render_plan([(i.slot, i.product.name) for i in self.items], provider.model, provider.whole_outfit)
        return [self.items[idx].id for idx, _ in plan]
