"""Subscription plan pricing/credits — one place to change, per the "pricing
should remain configurable rather than hardcoded everywhere" rule. FREE has
no entry here: it's the "no active subscription" state, not something you
subscribe to.

Prices are business decisions, not engineering ones — set by the product
owner, not invented here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import SubscriptionPlan


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    plan: SubscriptionPlan
    name: str
    price_cents: int
    currency: str
    credits_per_cycle: int


PLAN_DEFINITIONS: dict[SubscriptionPlan, PlanDefinition] = {
    SubscriptionPlan.STARTER: PlanDefinition(
        plan=SubscriptionPlan.STARTER, name="Starter", price_cents=799, currency="usd", credits_per_cycle=100
    ),
    SubscriptionPlan.PRO: PlanDefinition(
        plan=SubscriptionPlan.PRO, name="Pro", price_cents=1999, currency="usd", credits_per_cycle=300
    ),
    SubscriptionPlan.BUSINESS: PlanDefinition(
        plan=SubscriptionPlan.BUSINESS, name="Business", price_cents=4999, currency="usd", credits_per_cycle=1000
    ),
}
