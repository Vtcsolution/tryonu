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


class PurchaseCreditsRequest(BaseModel):
    credit_package_id: str
