from __future__ import annotations

from datetime import datetime

from app.schemas.common import ORMModel
from app.schemas.product import ProductOut


class SavedLookOut(ORMModel):
    id: str
    title: str | None
    image_url: str | None
    product: ProductOut | None
    created_at: datetime
