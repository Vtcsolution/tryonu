from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import SubscriptionPlan, SubscriptionStatus
from app.schemas.common import ORMModel


class PlanOut(BaseModel):
    plan: SubscriptionPlan
    name: str
    price_cents: int
    currency: str
    credits_per_cycle: int


class SubscribeRequest(BaseModel):
    plan: SubscriptionPlan


class SubscriptionOut(ORMModel):
    id: str
    plan: SubscriptionPlan
    status: SubscriptionStatus
    credits_per_cycle: int
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    created_at: datetime


class SubscribeResponse(BaseModel):
    subscription: SubscriptionOut
    client_secret: str | None = None
