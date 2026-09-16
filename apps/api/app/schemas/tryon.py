from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import JobStatus
from app.schemas.common import ORMModel
from app.schemas.outfit import OutfitOut
from app.schemas.photo import UserPhotoOut
from app.schemas.product import ProductOut


class CreateTryOnRequest(BaseModel):
    user_photo_id: str
    product_id: str | None = None
    outfit_id: str | None = None


class CreateMultiTryOnRequest(BaseModel):
    """One job per photo, same product/outfit — e.g. front + back angles.
    Charged per job (2 photos = double the cost of one), checked upfront
    against the whole batch, not partially charged if a later one fails."""

    user_photo_ids: list[str]
    product_id: str | None = None
    outfit_id: str | None = None


class TryOnResultOut(ORMModel):
    id: str
    image_url: str
    width: int | None
    height: int | None


class TryOnJobOut(ORMModel):
    id: str
    status: JobStatus
    provider: str
    provider_model: str
    credit_cost: int
    error_message: str | None
    product: ProductOut | None
    outfit: OutfitOut | None
    result: TryOnResultOut | None
    user_photo: UserPhotoOut
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
