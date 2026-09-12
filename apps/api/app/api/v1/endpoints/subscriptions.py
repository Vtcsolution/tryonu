from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.plans import PLAN_DEFINITIONS
from app.core.time import utcnow
from app.models.enums import CreditReason, PaymentStatus, SubscriptionStatus
from app.models.subscription import Payment, Subscription
from app.payments.registry import get_payment_provider
from app.schemas.common import Message
from app.schemas.subscription import PlanOut, SubscribeRequest, SubscribeResponse, SubscriptionOut
from app.services import credit_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

_LIVE_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE)


@router.get("/plans", response_model=list[PlanOut])
async def list_plans():
    return [
        PlanOut(plan=p.plan, name=p.name, price_cents=p.price_cents, currency=p.currency, credits_per_cycle=p.credits_per_cycle)
        for p in PLAN_DEFINITIONS.values()
    ]


@router.get("/me", response_model=SubscriptionOut | None)
async def my_subscription(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.status.in_(_LIVE_STATUSES))
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


@router.post("/subscribe", response_model=SubscribeResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(payload: SubscribeRequest, user: CurrentUser, db: DbSession):
    plan_def = PLAN_DEFINITIONS.get(payload.plan)
    if plan_def is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a subscribable plan")

    existing = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id, Subscription.status.in_(_LIVE_STATUSES))
    )
    if existing.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already has an active subscription — cancel it before subscribing to a different plan",
        )

    provider = get_payment_provider()
    checkout = await provider.create_subscription(
        price_cents=plan_def.price_cents,
        currency=plan_def.currency,
        interval="month",
        product_name=f"TryOnU {plan_def.name}",
        user_id=user.id,
        customer_email=user.email,
        metadata={"plan": plan_def.plan.value},
    )

    now = utcnow()
    sub = Subscription(
        user_id=user.id,
        plan=plan_def.plan,
        status=SubscriptionStatus.ACTIVE if checkout.status == "active" else SubscriptionStatus.INCOMPLETE,
        credits_per_cycle=plan_def.credits_per_cycle,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        external_subscription_id=checkout.external_subscription_id,
    )
    db.add(sub)
    await db.flush()

    db.add(
        Payment(
            user_id=user.id,
            amount_cents=plan_def.price_cents,
            currency=plan_def.currency,
            status=PaymentStatus.SUCCEEDED if checkout.status == "active" else PaymentStatus.PENDING,
            provider=provider.name,
            external_payment_id=checkout.external_subscription_id,
            subscription_id=sub.id,
        )
    )

    if checkout.status == "active":
        # Real Stripe path grants on the webhook only (see webhooks.py) —
        # the mock/instant path has no webhook to wait for, so grant here.
        await credit_service.grant(
            db,
            user_id=user.id,
            amount=plan_def.credits_per_cycle,
            reason=CreditReason.SUBSCRIPTION_GRANT,
            reference_type="subscription",
            reference_id=sub.id,
            note=f"Subscribed to {plan_def.name}",
        )

    await db.commit()
    await db.refresh(sub)
    return SubscribeResponse(subscription=sub, client_secret=checkout.client_secret)


@router.post("/cancel", response_model=Message)
async def cancel(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id, Subscription.status.in_(_LIVE_STATUSES))
    )
    sub = result.scalars().first()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription")

    provider = get_payment_provider()
    if sub.external_subscription_id:
        try:
            await provider.cancel_subscription(sub.external_subscription_id)
        except NotImplementedError:
            pass

    sub.cancel_at_period_end = True
    await db.commit()
    return Message(detail="Your subscription will not renew after the current period ends.")
