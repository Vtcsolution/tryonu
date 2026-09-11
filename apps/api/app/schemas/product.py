from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Availability, Gender
from app.schemas.common import ORMModel


class RetailerOut(ORMModel):
    id: str
    slug: str
    name: str
    logo_url: str | None


class ProductImageOut(ORMModel):
    url: str
    position: int
    is_primary: bool


class ProductOut(ORMModel):
    id: str
    name: str
    brand: str | None
    description: str | None
    category_id: str | None
    subcategory: str | None
    gender: Gender
    color: str | None
    sizes: list[str] | None
    style_tags: list[str] | None
    price_cents: int
    currency: str
    rating: float | None
    rating_count: int
    availability: Availability
    product_url: str
    images: list[ProductImageOut]
    retailer: RetailerOut
    created_at: datetime

    @property
    def price(self) -> float:
        return self.price_cents / 100


class ProductSearchFilters(BaseModel):
    q: str | None = None
    category: str | None = None
    brand: str | None = None
    color: str | None = None
    gender: Gender | None = None
    retailer: str | None = None
    min_price_cents: int | None = None
    max_price_cents: int | None = None
    style: str | None = None
    sort: str = "relevance"  # relevance | price_asc | price_desc | rating | newest
    limit: int = 24
    offset: int = 0
