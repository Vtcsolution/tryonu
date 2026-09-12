from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import JobStatus
from app.schemas.common import ORMModel
from app.schemas.product import ProductOut


class CreateTryOnRequest(BaseModel):
    user_photo_id: str
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
    result: TryOnResultOut | None
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
