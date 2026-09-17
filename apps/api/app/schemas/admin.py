from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AuthProvider
from app.schemas.common import ORMModel
from app.schemas.credit import CreditTransactionOut
from app.schemas.tryon import TryOnJobOut


class AdminTryOnJobOut(TryOnJobOut):
    user_email: str | None = None


class AdminUserOut(ORMModel):
    id: str
    email: str
    full_name: str | None
    auth_provider: AuthProvider
    is_active: bool
    is_admin: bool
    email_verified: bool
    credits_balance: int
    last_login_at: datetime | None
    created_at: datetime


class AdminUserDetail(BaseModel):
    user: AdminUserOut
    tryon_jobs_total: int
    photos_total: int
    wardrobe_items_total: int
    affiliate_clicks_total: int
    recent_transactions: list[CreditTransactionOut]


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
    email_verified: bool | None = None


class AdminCreditAdjustment(BaseModel):
    # signed: positive grants, negative removes
    amount: int = Field(ge=-100_000, le=100_000)
    note: str = Field(min_length=3, max_length=200)


class AdminProductOut(BaseModel):
    id: str
    name: str
    brand: str | None
    retailer_slug: str
    retailer_name: str
    price_cents: int
    currency: str
    image_url: str | None
    product_url: str
    is_active: bool
    created_at: datetime


class AdminProductUpdate(BaseModel):
    is_active: bool


class AdminRetailerOut(BaseModel):
    slug: str
    name: str
    is_active: bool
    base_commission_pct: float | None
    affiliate_network: str | None
    # does the adapter actually implement live search, or is it still a stub?
    integration_built: bool
    credentials_configured: bool
    # None when the retailer has no separate commission-tracking id to set
    commission_tracking_configured: bool | None
    saved_products: int


class AdminRetailerUpdate(BaseModel):
    is_active: bool | None = None
    base_commission_pct: float | None = Field(default=None, ge=0, le=100)


class AdminCreditPackageOut(ORMModel):
    id: str
    name: str
    credits: int
    price_cents: int
    currency: str
    is_active: bool
    created_at: datetime


class AdminCreditPackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    credits: int = Field(gt=0, le=1_000_000)
    price_cents: int = Field(gt=0, le=100_000_00)
    currency: str = Field(default="usd", min_length=3, max_length=8)


class AdminCreditPackageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    credits: int | None = Field(default=None, gt=0, le=1_000_000)
    price_cents: int | None = Field(default=None, gt=0, le=100_000_00)
    is_active: bool | None = None


class AdminSystemStatus(BaseModel):
    env: str
    tryon_provider: str
    fashn_model: str
    llm_provider: str
    payment_provider: str
    email_provider: str
    storage: str
    job_queue: str
    signup_free_credits: int
    tryon_credit_cost: int
    outfit_tryon_credit_cost: int


class AdminAuditLogOut(BaseModel):
    id: str
    admin_email: str | None
    action: str
    target_type: str
    target_id: str
    detail: dict | None
    created_at: datetime


class AdminOverview(BaseModel):
    total_users: int
    new_users_7d: int
    active_subscriptions: int
    total_credits_outstanding: int
    tryon_jobs_total: int
    tryon_jobs_24h: int
    tryon_jobs_failed_24h: int
    tryon_jobs_by_status: dict[str, int]
    total_products: int
    active_retailers: int
    affiliate_clicks_total: int
    affiliate_clicks_7d: int
    revenue_cents_total: int
    revenue_cents_30d: int
    revenue_cents_subscriptions_30d: int
    revenue_cents_one_off_30d: int
    ai_cost_usd_cents_30d: float
    ai_calls_30d: int
