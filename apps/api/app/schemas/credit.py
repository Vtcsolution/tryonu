from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CreditReason
from app.schemas.common import ORMModel


class CreditTransactionOut(ORMModel):
    id: str
    amount: int
    balance_after: int
    reason: CreditReason
    reference_type: str | None
    reference_id: str | None
    note: str | None
    created_at: datetime


class CreditBalanceOut(BaseModel):
    balance: int


class CreditPackageOut(ORMModel):
    id: str
    name: str
    credits: int
    price_cents: int
    currency: str


class CreditPricingOut(BaseModel):
    """What a try-on costs in credits right now (admin-editable)."""

    tryon_cost: int
    outfit_tryon_cost: int


class PurchaseCreditsRequest(BaseModel):
    credit_package_id: str


class PurchaseCreditsResponse(BaseModel):
    payment_id: str
    status: str  # "succeeded" | "requires_action" | "pending" | "failed"
    # Set only for "requires_action" — the frontend confirms the payment
    # with Stripe.js using this, then polls GET /credits/purchase/{payment_id}.
    client_secret: str | None = None
    checkout_url: str | None = None
    # Set only once status == "succeeded".
    credits_granted: int | None = None
    new_balance: int | None = None
    # a store plan payment: the plan unlocked and until when
    plan_name: str | None = None
    plan_expires_at: datetime | None = None
    # a developer API pack: how many try-ons it added
    developer_tryons: int | None = None
