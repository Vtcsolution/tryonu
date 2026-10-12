from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

_COUNTRY = r"^[A-Za-z]{2}$"
_GENDER = r"^(women|men|unisex|girls|boys)$"


class StorePlanOut(BaseModel):
    id: str
    code: str
    name: str
    price_cents: int
    currency: str
    product_limit: int
    duration_days: int
    is_active: bool = True


class StoreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    country: str = Field(pattern=_COUNTRY)
    description: str | None = Field(default=None, max_length=2000)
    website_url: str | None = Field(default=None, max_length=1024)
    contact_email: str | None = Field(default=None, max_length=255)


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    country: str | None = Field(default=None, pattern=_COUNTRY)
    description: str | None = Field(default=None, max_length=2000)
    website_url: str | None = Field(default=None, max_length=1024)
    contact_email: str | None = Field(default=None, max_length=255)


class StoreOut(BaseModel):
    id: str
    name: str
    slug: str
    country: str
    description: str | None
    website_url: str | None
    contact_email: str | None
    logo_url: str | None
    status: str
    status_note: str | None
    plan_code: str | None
    plan_product_limit: int
    plan_expires_at: datetime | None
    plan_active: bool
    live: bool
    product_count: int
    feed_url: str | None
    feed_last_run_at: datetime | None
    feed_last_result: str | None
    auto_renew: bool = False
    subscription_status: str | None = None
    subscription_plan_code: str | None = None


class StoreProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=512)
    description: str | None = Field(default=None, max_length=4000)
    price_cents: int = Field(gt=0, le=100_000_000)
    currency: str = Field(default="usd", min_length=3, max_length=8)
    product_url: str = Field(min_length=8, max_length=2048)
    category: str | None = Field(default=None, max_length=120)
    gender: str = Field(default="unisex", pattern=_GENDER)
    color: str | None = Field(default=None, max_length=60)
    is_active: bool = True


class StoreProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=512)
    description: str | None = Field(default=None, max_length=4000)
    price_cents: int | None = Field(default=None, gt=0, le=100_000_000)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    product_url: str | None = Field(default=None, min_length=8, max_length=2048)
    category: str | None = Field(default=None, max_length=120)
    gender: str | None = Field(default=None, pattern=_GENDER)
    color: str | None = Field(default=None, max_length=60)
    is_active: bool | None = None


class StoreProductOut(BaseModel):
    id: str
    source: str
    name: str
    description: str | None
    price_cents: int
    currency: str
    images: list[str]
    product_url: str
    category: str | None
    gender: str
    color: str | None
    is_active: bool
    updated_at: datetime


class StoreFeedIn(BaseModel):
    feed_url: str | None = Field(default=None, max_length=2048)


class StoreFeedResult(BaseModel):
    result: str


class AdminStoreOut(StoreOut):
    owner_email: str
    created_at: datetime


class AdminStoreStatusIn(BaseModel):
    status: str = Field(pattern=r"^(pending|approved|rejected|suspended)$")
    note: str | None = Field(default=None, max_length=1000)


class AdminStorePlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    price_cents: int | None = Field(default=None, gt=0, le=100_000_00)
    product_limit: int | None = Field(default=None, gt=0, le=1_000_000)
    duration_days: int | None = Field(default=None, gt=0, le=3650)
    is_active: bool | None = None


class StoreStatsTop(BaseModel):
    store_product_id: str
    name: str
    views: int = 0
    clicks: int
    tryons: int


class StoreStatsOut(BaseModel):
    days: int
    views: int = 0
    clicks: int
    tryons: int
    top: list[StoreStatsTop]


class StorePaymentOut(BaseModel):
    id: str
    amount_cents: int
    currency: str
    status: str
    plan_name: str | None
    created_at: datetime


class PublicStoreOut(BaseModel):
    name: str
    slug: str
    country: str
    description: str | None
    website_url: str | None
    logo_url: str | None
    products: list[StoreProductOut]


class SelectedProductOut(BaseModel):
    product_id: str


class AdminStoreDetailOut(AdminStoreOut):
    stats: StoreStatsOut
    payments: list[StorePaymentOut]
    products: list[StoreProductOut]


class AdminGrantPlanIn(BaseModel):
    plan_code: str = Field(min_length=1, max_length=32)
    days: int = Field(gt=0, le=3650)


class AdminProductToggleIn(BaseModel):
    is_active: bool


class AdminStoreSummaryOut(BaseModel):
    by_status: dict[str, int]
    live: int
    products: int
    plan_revenue: dict[str, int]  # currency -> cents, succeeded store plan payments


class SubscriptionStartOut(BaseModel):
    checkout_url: str


class SubscriptionSyncOut(BaseModel):
    result: str
    store: StoreOut
