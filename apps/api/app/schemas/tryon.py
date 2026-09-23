from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import JobStatus
from app.schemas.common import ORMModel
from app.schemas.outfit import OutfitOut
from app.schemas.photo import UserPhotoOut
from app.schemas.product import ProductOut
from app.schemas.wardrobe import WardrobeItemOut


class CreateTryOnRequest(BaseModel):
    user_photo_id: str
    product_id: str | None = None
    outfit_id: str | None = None
    wardrobe_item_id: str | None = None


class CreateMultiTryOnRequest(BaseModel):
    """One job per photo, same product/outfit/wardrobe item — e.g. front +
    back angles. Charged per job (2 photos = double the cost of one),
    checked upfront against the whole batch, not partially charged if a
    later one fails."""

    user_photo_ids: list[str]
    product_id: str | None = None
    outfit_id: str | None = None
    wardrobe_item_id: str | None = None


class ResultPlacement(BaseModel):
    """One item on the finished photo. `box` is [x0, y0, x1, y1] in
    fractions of the image, so a client can label it at any size."""

    name: str
    product_id: str | None = None
    slot: str | None = None
    drawn: bool = False
    box: list[float] | None = None


class TryOnResultOut(ORMModel):
    id: str
    image_url: str
    width: int | None
    height: int | None
    placements: list[ResultPlacement] | None = None


class TryOnJobOut(ORMModel):
    id: str
    status: JobStatus
    provider: str
    provider_model: str
    credit_cost: int
    error_message: str | None
    product: ProductOut | None
    outfit: OutfitOut | None
    wardrobe_item: WardrobeItemOut | None
    result: TryOnResultOut | None
    user_photo: UserPhotoOut
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    @model_validator(mode="after")
    def _labels_match_what_was_drawn(self) -> "TryOnJobOut":
        # a finished job's "on photo" labels follow the engine that actually
        # drew it (e.g. FASHN after an OpenAI fallback), not today's config
        if self.outfit is not None and self.status == JobStatus.COMPLETED:
            self.outfit.drawn_by(self.provider, self.provider_model)
        return self
