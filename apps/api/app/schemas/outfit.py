from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import OutfitSlot
from app.schemas.common import ORMModel
from app.schemas.product import ProductOut
from app.services.outfit_slots import WHOLE_OUTFIT_PROVIDERS, render_plan


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

    # Items the try-on will actually draw on the photo — the rest are shown
    # alongside as matched products. Same plan the worker uses, so the
    # "on photo" labels never over-promise; a finished try-on's response
    # replaces it with what that job's engine really drew.
    rendered_item_ids: list[str] = []

    @model_validator(mode="after")
    def _plan_render(self) -> "OutfitOut":
        from app.ai.providers.registry import plan_outfit_render

        _, plan = plan_outfit_render([(i.slot, i.product.name) for i in self.items])
        self.rendered_item_ids = [self.items[idx].id for idx, _ in plan]
        return self

    def drawn_by(self, provider_name: str, model: str) -> None:
        plan = render_plan([(i.slot, i.product.name) for i in self.items], model, provider_name in WHOLE_OUTFIT_PROVIDERS)
        self.rendered_item_ids = [self.items[idx].id for idx, _ in plan]
