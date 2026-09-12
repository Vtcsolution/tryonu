from __future__ import annotations

from pydantic import BaseModel


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
