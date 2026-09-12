"""Shared enums, stored as plain VARCHAR (native_enum=False) so the exact
same model works unmodified on SQLite (dev) and PostgreSQL (prod) — no
Postgres ALTER TYPE migrations when a value is added.
"""

from __future__ import annotations

from enum import StrEnum


class AuthProvider(StrEnum):
    LOCAL = "local"
    GOOGLE = "google"


class PhotoKind(StrEnum):
    FRONT = "front"
    FULL_BODY = "full_body"
    LEFT_SIDE = "left_side"
    RIGHT_SIDE = "right_side"
    LEFT_45 = "left_45"
    RIGHT_45 = "right_45"
    BACK = "back"
    EXTRA = "extra"


class CreditReason(StrEnum):
    SIGNUP_BONUS = "signup_bonus"
    TRYON_DEBIT = "tryon_debit"
    TRYON_REFUND = "tryon_refund"
    PURCHASE = "purchase"
    SUBSCRIPTION_GRANT = "subscription_grant"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class SubscriptionPlan(StrEnum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"


class SubscriptionStatus(StrEnum):
    INCOMPLETE = "incomplete"  # created, awaiting the first invoice's card confirmation (real Stripe only)
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class Gender(StrEnum):
    MEN = "men"
    WOMEN = "women"
    UNISEX = "unisex"
    KIDS = "kids"


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutfitSlot(StrEnum):
    TOP = "top"
    BOTTOM = "bottom"
    DRESS = "dress"
    OUTERWEAR = "outerwear"
    SHOES = "shoes"
    WATCH = "watch"
    BAG = "bag"
    ACCESSORY = "accessory"
    OTHER = "other"


class AffiliateSource(StrEnum):
    PRODUCT_CARD = "product_card"
    TRYON_RESULT = "tryon_result"
    OUTFIT = "outfit"
    SEARCH = "search"
    STYLIST = "stylist"


class AIUsageKind(StrEnum):
    VIRTUAL_TRYON = "virtual_tryon"
    STYLIST_LLM = "stylist_llm"
    EMBEDDING = "embedding"
