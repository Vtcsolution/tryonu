from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DeveloperAccountIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    website: str | None = Field(default=None, max_length=1024)


class DeveloperAccountOut(BaseModel):
    id: str
    company_name: str
    website: str | None
    credits: int
    status: str
    tryons_total: int = 0
    tryons_30d: int = 0
    created_at: datetime


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    # secret: for your server | public: for a web page (the widget), only on these domains
    kind: str = Field(default="secret", pattern=r"^(secret|public)$")
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)


class ApiKeyOut(BaseModel):
    id: str
    name: str
    kind: str
    prefix: str
    allowed_domains: list[str] = []
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreatedOut(ApiKeyOut):
    # shown once: only a fingerprint is kept
    key: str


class CreditPackOut(BaseModel):
    id: str
    code: str
    name: str
    tryons: int
    price_cents: int
    currency: str
    is_active: bool = True


class CreditPackUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    tryons: int | None = Field(default=None, gt=0, le=1_000_000)
    price_cents: int | None = Field(default=None, gt=0, le=100_000_000)
    is_active: bool | None = None


class UsageOut(BaseModel):
    id: str  # the try-on's id, as the API returns it
    status: str
    reference: str | None
    credits: int
    refunded: bool
    result_image_url: str | None
    error: str | None
    created_at: datetime


class DeveloperPaymentOut(BaseModel):
    id: str
    amount_cents: int
    currency: str
    status: str
    pack_name: str | None
    tryons: int | None
    created_at: datetime


# ------------------------------------------------------------------ public API


class PublicTryOnIn(BaseModel):
    person_image_url: str = Field(min_length=8, max_length=2048)
    garment_image_url: str = Field(min_length=8, max_length=2048)
    garment_name: str | None = Field(default=None, max_length=255)
    reference: str | None = Field(default=None, max_length=120)


class PublicTryOnOut(BaseModel):
    id: str
    status: str  # queued | processing | completed | failed
    result_image_url: str | None = None
    error: str | None = None
    reference: str | None = None
    credits_used: int = 1
    credits_left: int | None = None
    created_at: datetime
    completed_at: datetime | None = None


class PublicCreditsOut(BaseModel):
    credits_left: int


# ------------------------------------------------------------------ admin


class AdminDeveloperOut(DeveloperAccountOut):
    owner_email: str
    keys: int = 0


class AdminCreditsIn(BaseModel):
    amount: int = Field(ge=-1_000_000, le=1_000_000)
    # why, for the record and the developer's notification ("Launch partner")
    note: str | None = Field(default=None, max_length=200)


class AdminStatusIn(BaseModel):
    status: str = Field(pattern=r"^(active|suspended)$")
