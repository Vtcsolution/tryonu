from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import SavedProductStatus
from app.schemas.common import ORMModel


class SaveProductRequest(BaseModel):
    """Either a product we already hold (`product_id`), or a live search
    result identified by retailer + id + the query that found it — which
    is re-fetched from the retailer before anything is saved."""

    status: SavedProductStatus = SavedProductStatus.SAVED
    product_id: str | None = None
    retailer_slug: str | None = None
    retailer_product_id: str | None = None
    query: str | None = None

    @model_validator(mode="after")
    def _one_way_or_the_other(self) -> "SaveProductRequest":
        live = (self.retailer_slug, self.retailer_product_id, self.query)
        if self.product_id and any(live):
            raise ValueError("give either product_id or a live result, not both")
        if not self.product_id and not all(live):
            raise ValueError("a live result needs retailer_slug, retailer_product_id and query")
        return self


class UpdateSavedProductRequest(BaseModel):
    status: SavedProductStatus


class SavedProductOut(ORMModel):
    id: str
    status: SavedProductStatus
    product_id: str | None
    retailer_slug: str
    retailer_name: str
    retailer_product_id: str
    name: str
    image_url: str | None
    product_url: str
    # deliberately not exposed: affiliate_url. Clients open a saved product
    # through GET /saved-products/{id}/go so the click is recorded and the
    # tracking can never be lost by a client rebuilding the link itself.
    price_cents: int
    currency: str
    created_at: datetime
    updated_at: datetime | None = None
