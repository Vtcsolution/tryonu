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

    def drawn_from_placements(self, placements: list) -> None:
        """A completed job's real, per-item outcome — which of this
        outfit's products the render actually placed and the quality
        inspector actually verified, not which ones a plan predicted it
        would attempt. `placements` is a completed TryOnResult's own
        list (see tryon_tasks._placements): matched back to this
        outfit's items by product id, the same key it already carries.
        Call this instead of drawn_by() whenever a real result exists —
        drawn_by()'s plan is a guess about what a job WOULD draw, made
        before it runs; this is what one actually did."""
        applied = {p.product_id for p in placements if p.drawn and p.product_id}
        self.rendered_item_ids = [i.id for i in self.items if i.product.id in applied]
