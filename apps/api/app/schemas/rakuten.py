from __future__ import annotations

from pydantic import BaseModel


class RakutenStatusOut(BaseModel):
    enabled: bool
    configured: bool
    # Never the credentials themselves — only which ones are present, so
    # an admin can diagnose a misconfiguration without secrets ever
    # leaving the server.
    has_client_credentials: bool
    has_direct_token: bool
    has_publisher_id: bool
    has_account_id: bool
    base_url: str


class RakutenProductPreviewOut(BaseModel):
    retailer_product_id: str
    name: str
    brand: str | None
    merchant_name: str | None
    merchant_id: str | None
    price_cents: int
    currency: str
    product_url: str
    images: list[str]
    category_slug: str | None


class RakutenAdvertiserOut(BaseModel):
    mid: str
    name: str
    url: str | None
    countries_shipped_to: list[str] | None
    has_product_feed: bool | None
    supports_deep_linking: bool | None
    accepts_partnerships: bool | None
    status: str | None


class RakutenPartnershipOut(BaseModel):
    mid: str
    advertiser_name: str
    status: str
    updated_at: str | None


class RakutenOfferOut(BaseModel):
    id: str
    mid: str
    title: str
    description: str | None
    start_date: str | None
    end_date: str | None
    commission_rate: str | None
    commission_type: str | None


class RakutenCouponOut(BaseModel):
    id: str
    mid: str
    advertiser_name: str
    description: str
    code: str | None
    start_date: str | None
    end_date: str | None
