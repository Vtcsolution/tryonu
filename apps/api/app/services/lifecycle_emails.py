"""The emails the site sends by itself, so nobody has to remember to:

- welcome: once a member confirmed their email, how to get their first look
- first_look: two days later, if they haven't tried anything on yet (with the
  $1 first outfit when they've never bought)
- look_ready: an hour after a finished try-on, a nudge to shop the pieces
  (at most one every three days)
- the weekly trending looks email to every member who gets emails (into the
  Send email queue, so it goes out slowly)
- receipt: right after a credit pack is paid (sent even to members who turned
  emails off: it's a receipt)
- unfinished_payment: a few hours after a payment was started and never finished
- win_back: 30 days without a visit, new looks (at most every 60 days)
- shop owners: their plan ends in 3 days (unless it renews by itself), and on
  Mondays last week's numbers for their store

Each goes to each member once (user_email_events), only to members who keep
emails on, always with the "stop these emails" link, and within the site's
email limits (email_budget), a few seconds apart."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.email.templates import action_email
from app.models.admin_email import AdminEmail
from app.models.email_event import UserEmailEvent
from app.models.enums import JobStatus, PaymentStatus
from app.models.subscription import Payment
from app.models.tryon import TryOnJob
from app.models.user import User
from app.services import email_budget

RUN_EVERY_SECONDS = 10 * 60  # often enough for a receipt to arrive within minutes
PER_ROUND = 40  # the most automatic emails in one round (the hourly limit is shared)
PAUSE = 3.0  # seconds between two emails: never a burst


def _tracked(path: str, campaign: str) -> str:
    from app.services.admin_email_service import tracked

    return tracked(path, campaign)


def _first(user: User) -> str:
    return user.full_name.split()[0] if user.full_name and user.full_name.strip() else "there"


def _members():
    return and_(User.is_active.is_(True), User.notify_email.is_(True), User.team_person.is_(False))


def _not_sent(kind: str, ref: str = ""):
    return ~exists().where(UserEmailEvent.user_id == User.id, UserEmailEvent.kind == kind, UserEmailEvent.ref == ref)


async def _paid(db: AsyncSession, user_id: str) -> bool:
    return (
        await db.scalar(select(Payment.id).where(Payment.user_id == user_id, Payment.status == PaymentStatus.SUCCEEDED).limit(1))
    ) is not None


async def _send(
    db: AsyncSession,
    user: User,
    kind: str,
    subject: str,
    mail: tuple[str, str],
    ref: str = "",
    *,
    to: str | None = None,
    marketing: bool = True,
) -> bool:
    """Marks it sent first (so a crash never sends twice), then sends.
    to: another address (a store's contact email); marketing: carries the
    "stop these emails" link (a receipt doesn't)."""
    from app.email.registry import get_email_provider
    from app.services.notification_service import unsubscribe_url

    db.add(UserEmailEvent(user_id=user.id, kind=kind, ref=ref))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False
    if not await email_budget.take(db):
        await db.rollback()
        return False
    text, page = mail
    try:
        await get_email_provider().send(
            to=to or user.email, subject=subject, text_body=text, html_body=page,
            unsubscribe_url=unsubscribe_url(user.id) if marketing else None,
        )
    except Exception as exc:  # noqa: BLE001 - tried again next round
        await db.rollback()
        logger.warning("lifecycle_email_failed", kind=kind, user_id=user.id, error=str(exc)[:200])
        if email_budget.slow_down(exc):
            raise
        return False
    await db.commit()
    return True


def _footer(user: User) -> str:
    from app.services.notification_service import unsubscribe_url

    return f"You get this because you have a TryOnU account. Stop these emails: {unsubscribe_url(user.id)}"


async def _welcome(db: AsyncSession, limit: int) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=14)
    users = (
        await db.execute(
            select(User).where(_members(), User.email_verified.is_(True), User.created_at >= since, _not_sent("welcome")).limit(limit)
        )
    ).scalars().all()
    sent = 0
    for user in users:
        mail = action_email(
            f"Welcome to TryOnU, {_first(user)}!",
            [
                "Here's how to get your first look:",
                "1. Pick an outfit from Ready looks, or search any product.",
                "2. Upload one clear photo of you, standing.",
                "3. See the whole outfit on you in about a minute, then buy only the pieces you love.",
            ],
            "Pick my first look",
            _tracked("/looks", "welcome"),
            after=["New here? Your first complete outfit costs just $1."],
            footer=_footer(user),
        )
        if await _send(db, user, "welcome", "Welcome to TryOnU: your first look in 3 steps", mail):
            sent += 1
            await asyncio.sleep(PAUSE)
    return sent


async def _first_look(db: AsyncSession, limit: int) -> int:
    now = datetime.now(timezone.utc)
    tried = exists().where(TryOnJob.user_id == User.id)
    users = (
        await db.execute(
            select(User)
            .where(
                _members(), User.email_verified.is_(True), User.created_at <= now - timedelta(days=2),
                User.created_at >= now - timedelta(days=30), ~tried, _not_sent("first_look"),
            )
            .limit(limit)
        )
    ).scalars().all()
    sent = 0
    for user in users:
        if await _paid(db, user.id):
            lines = ["Your first look is still waiting. Upload one photo and see a whole outfit on you, before you buy a thing."]
            button, url = "Try a look on you", _tracked("/looks", "first_look")
        else:
            lines = [
                "Your first look is still waiting. Upload one photo and see a whole outfit on you, before you buy a thing.",
                "Your first complete outfit costs just $1: 10 credits, enough for one whole look.",
            ]
            button, url = "Get my first outfit for $1", _tracked("/credits?offer=1", "first_look")
        mail = action_email(f"{_first(user)}, see it on you first", lines, button, url, footer=_footer(user))
        if await _send(db, user, "first_look", "Your first outfit is waiting (just $1)", mail):
            sent += 1
            await asyncio.sleep(PAUSE)
    return sent


async def _look_ready(db: AsyncSession, limit: int) -> int:
    now = datetime.now(timezone.utc)
    recent = exists().where(
        UserEmailEvent.user_id == User.id, UserEmailEvent.kind == "look_ready", UserEmailEvent.created_at >= now - timedelta(days=3)
    )
    rows = (
        await db.execute(
            select(TryOnJob, User)
            .join(User, User.id == TryOnJob.user_id)
            .where(
                _members(), User.is_team.is_(False), User.is_admin.is_(False),
                TryOnJob.status == JobStatus.COMPLETED,
                TryOnJob.completed_at <= now - timedelta(hours=1), TryOnJob.completed_at >= now - timedelta(days=2),
                ~recent,
                ~exists().where(UserEmailEvent.user_id == User.id, UserEmailEvent.kind == "look_ready", UserEmailEvent.ref == TryOnJob.id),
            )
            .order_by(TryOnJob.completed_at.desc())
            .limit(limit)
        )
    ).all()
    sent, done = 0, set()
    for job, user in rows:
        if user.id in done:
            continue
        done.add(user.id)
        mail = action_email(
            "Your look is ready",
            [
                f"Hi {_first(user)}, your try-on is waiting for you on TryOnU.",
                "Every piece is a real product from a real shop. Open your look to buy the ones you love, swap a piece, "
                "or share it and ask friends: buy or skip?",
            ],
            "See my look and shop it",
            _tracked(f"/try?job={job.id}", "look_ready"),
            footer=_footer(user),
        )
        if await _send(db, user, "look_ready", "Your look is ready: shop the pieces", mail, ref=job.id):
            sent += 1
            await asyncio.sleep(PAUSE)
    return sent


async def _weekly_looks(db: AsyncSession) -> bool:
    """Friday morning (UTC): this week's trending looks to every member who
    gets emails, through the Send email queue (it goes out slowly)."""
    from app.services import admin_email_service as svc
    from app.services.looks_email import pick_looks

    now = datetime.now(timezone.utc)
    if now.weekday() != 4 or now.hour < 9:
        return False
    already = await db.scalar(
        select(AdminEmail.id).where(
            AdminEmail.created_by_id.is_(None), AdminEmail.template == "looks", AdminEmail.created_at >= now - timedelta(days=6)
        )
    )
    if already:
        return False
    looks = await pick_looks(db, "")
    if len(looks) < 2:
        return False
    people = await svc.recipients(db, "members", me=None)
    if not people:
        return False
    row = AdminEmail(
        audience="members",
        subject="This week's top looks on TryOnU",
        message=(
            "Hi {name},\n\nThese are the looks everyone is trying on TryOnU this week. Pick one, upload one photo, "
            "and see the whole outfit on you in about a minute, before you buy a single piece."
        ),
        template="looks",
        total=len(people),
    )
    db.add(svc.queued_row(row, people[: svc.MAX_PER_SEND], looks))
    await db.commit()
    logger.info("weekly_looks_email_queued", people=len(people))
    return True


def _money(cents: int, currency: str) -> str:
    from app.services.looks_email import _money as fmt

    return fmt(cents, currency) or f"{cents / 100:.2f} {currency.upper()}"


async def _receipts(db: AsyncSession, limit: int) -> int:
    from app.models.credit import CreditPackage

    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Payment, User, CreditPackage)
            .join(User, User.id == Payment.user_id)
            .join(CreditPackage, CreditPackage.id == Payment.credit_package_id)
            .where(
                Payment.status == PaymentStatus.SUCCEEDED, Payment.updated_at >= now - timedelta(days=2),
                User.is_active.is_(True), User.team_person.is_(False),
                ~exists().where(UserEmailEvent.user_id == User.id, UserEmailEvent.kind == "receipt", UserEmailEvent.ref == Payment.id),
            )
            .limit(limit)
        )
    ).all()
    sent = 0
    for payment, user, pack in rows:
        mail = action_email(
            "Thank you! Your credits are ready",
            [
                f"Hi {_first(user)}, your payment went through. Here is your receipt:",
                f"{pack.name}: {pack.credits} credits",
                f"Paid: {_money(payment.amount_cents, payment.currency)} ({payment.provider.title()})",
                f"Date: {(payment.updated_at or now):%d %B %Y}",
                f"Your balance now: {user.credits_balance} credits.",
            ],
            "Try a look on you",
            _tracked("/looks", "receipt"),
            after=[f"Keep this email as your receipt. Questions about a payment? Write to {get_settings().BILLING_EMAIL}."],
            footer=f"Receipt for your TryOnU account ({user.email}).",
        )
        if await _send(db, user, "receipt", f"Your TryOnU receipt: {pack.credits} credits", mail, ref=payment.id, marketing=False):
            sent += 1
            await asyncio.sleep(PAUSE)
    return sent


async def _unfinished_payment(db: AsyncSession, limit: int) -> int:
    from app.models.credit import CreditPackage

    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Payment, User, CreditPackage)
            .join(User, User.id == Payment.user_id)
            .join(CreditPackage, CreditPackage.id == Payment.credit_package_id)
            .where(
                _members(), Payment.status == PaymentStatus.PENDING,
                Payment.created_at <= now - timedelta(hours=2), Payment.created_at >= now - timedelta(days=2),
                _not_sent("unfinished_payment"),
            )
            .order_by(Payment.created_at.desc())
            .limit(limit * 3)
        )
    ).all()
    sent, done = 0, set()
    for payment, user, pack in rows:
        if user.id in done or sent >= limit:
            continue
        done.add(user.id)
        # paid since (another try that went through): nothing to remind
        if await db.scalar(
            select(Payment.id).where(
                Payment.user_id == user.id, Payment.status == PaymentStatus.SUCCEEDED, Payment.created_at >= payment.created_at
            ).limit(1)
        ):
            continue
        first = not await _paid(db, user.id)
        mail = action_email(
            "You were one step away",
            [
                f"Hi {_first(user)}, you started buying {pack.name} ({pack.credits} credits) but the payment didn't finish.",
                "Nothing was charged. If something went wrong, you can try again in a minute, by card, PayPal, Apple Pay "
                "or Google Pay.",
                *(["Your first complete outfit costs just $1: 10 credits, enough for one whole look."] if first else []),
            ],
            "Finish my purchase",
            _tracked("/credits?offer=1" if first else "/credits", "unfinished_payment"),
            after=[f"Had a problem paying? Reply to this email or write to {get_settings().BILLING_EMAIL}, and we'll help."],
            footer=_footer(user),
        )
        if await _send(db, user, "unfinished_payment", "Your TryOnU purchase didn't finish", mail):
            sent += 1
            await asyncio.sleep(PAUSE)
    return sent


async def _win_back(db: AsyncSession, limit: int) -> int:
    from app.services.looks_email import pick_looks

    now = datetime.now(timezone.utc)
    quiet_since = now - timedelta(days=30)
    recent = exists().where(
        UserEmailEvent.user_id == User.id, UserEmailEvent.kind == "win_back", UserEmailEvent.created_at >= now - timedelta(days=60)
    )
    users = (
        await db.execute(
            select(User)
            .where(
                _members(), User.email_verified.is_(True), User.created_at <= quiet_since,
                (User.last_login_at.is_(None)) | (User.last_login_at <= quiet_since), ~recent,
            )
            .limit(limit)
        )
    ).scalars().all()
    if not users:
        return 0
    looks = await pick_looks(db, "", limit=1)
    sent = 0
    for user in users:
        mail = action_email(
            f"We miss you, {_first(user)}",
            [
                "There are new Ready looks on TryOnU: complete outfits from real shops, ready to try on your own photo.",
                "Pick one, upload one photo, and see the whole look on you in about a minute.",
            ],
            "See what's new",
            _tracked("/looks", "win_back"),
            picture=looks[0]["picture"] if looks else None,
            footer=_footer(user),
        )
        if await _send(db, user, "win_back", "New looks are waiting for you on TryOnU", mail, ref=f"{now:%Y-%m-%d}"):
            sent += 1
            await asyncio.sleep(PAUSE)
    return sent


async def _store_plans_ending(db: AsyncSession, limit: int) -> int:
    from app.models.store import Store

    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Store, User)
            .join(User, User.id == Store.owner_user_id)
            .where(
                Store.status == "approved", Store.plan_free.is_(False), Store.plan_expires_at.is_not(None),
                Store.plan_expires_at > now, Store.plan_expires_at <= now + timedelta(days=3),
                (Store.subscription_status.is_(None)) | (Store.subscription_status != "active"),
            )
            .limit(limit)
        )
    ).all()
    sent = 0
    for store, owner in rows:
        kind = f"plan_end_{store.plan_expires_at:%Y%m%d}"
        mail = action_email(
            f"{store.name}: your plan ends on {store.plan_expires_at:%d %B}",
            [
                f"Hi {_first(owner)}, the TryOnU plan for {store.name} ends on {store.plan_expires_at:%d %B %Y}.",
                "After that your products are hidden from shoppers. Renew now to keep them showing, with no gap.",
            ],
            "Renew my plan",
            _tracked("/business", "store_plan_ending"),
            after=[f"Questions? Write to {get_settings().SALES_EMAIL}."],
            footer=f"You get this because you have a store on TryOnU ({store.name}).",
        )
        if await _send(db, owner, kind, f"Your TryOnU store plan ends on {store.plan_expires_at:%d %B}", mail,
                       ref=store.id, to=store.contact_email or owner.email, marketing=False):
            sent += 1
            await asyncio.sleep(PAUSE)
    return sent


async def _store_weeks(db: AsyncSession, limit: int) -> int:
    """Mondays: last week's numbers for each approved store."""
    from sqlalchemy import func

    from app.models.store import Store, StoreProduct, StoreProductView, StoreTryOn

    now = datetime.now(timezone.utc)
    if now.weekday() != 0 or now.hour < 8:
        return 0
    week = now - timedelta(days=7)
    kind = f"store_week_{now:%G%V}"
    rows = (
        await db.execute(
            select(Store, User)
            .join(User, User.id == Store.owner_user_id)
            .where(
                Store.status == "approved",
                exists().where(StoreProduct.store_id == Store.id),
                ~exists().where(UserEmailEvent.user_id == User.id, UserEmailEvent.kind == kind, UserEmailEvent.ref == Store.id),
            )
            .limit(limit)
        )
    ).all()
    sent = 0
    for store, owner in rows:
        views = int(
            await db.scalar(
                select(func.coalesce(func.sum(StoreProductView.views), 0)).where(
                    StoreProductView.store_id == store.id, StoreProductView.day >= week.date()
                )
            )
            or 0
        )
        tries = int(
            await db.scalar(select(func.count()).select_from(StoreTryOn).where(StoreTryOn.store_id == store.id, StoreTryOn.created_at >= week))
            or 0
        )
        lines = [
            f"Hi {_first(owner)}, here is last week on TryOnU for {store.name}:",
            f"Product views: {views}",
            f"Try-ons of your products: {tries}",
        ]
        lines.append(
            "Tip: add more products and clear photos on a plain background; shoppers try on what they can see clearly."
            if views < 20
            else "Shoppers are looking: keep your prices and stock up to date so they can buy right away."
        )
        mail = action_email(
            f"Your week on TryOnU: {store.name}",
            lines,
            "Open my store",
            _tracked("/business", "store_week"),
            footer=f"You get this because you have a store on TryOnU ({store.name}).",
        )
        if await _send(db, owner, kind, f"{store.name} on TryOnU last week: {views} views, {tries} try-ons", mail,
                       ref=store.id, to=store.contact_email or owner.email, marketing=False):
            sent += 1
            await asyncio.sleep(PAUSE)
    return sent


async def run_once(db: AsyncSession) -> dict:
    s = get_settings()
    out = {
        "receipt": 0, "welcome": 0, "unfinished_payment": 0, "look_ready": 0, "first_look": 0, "win_back": 0,
        "store_plan": 0, "store_week": 0, "weekly": False,
    }
    if s.WEEKLY_LOOKS_EMAIL_ON:
        out["weekly"] = await _weekly_looks(db)
    left = PER_ROUND
    # a receipt always goes, whatever the automatic-emails switch says
    out["receipt"] = await _receipts(db, left)
    left -= out["receipt"]
    if not s.AUTO_EMAILS_ON:
        return out
    for kind, step in (
        ("welcome", _welcome), ("unfinished_payment", _unfinished_payment), ("look_ready", _look_ready),
        ("first_look", _first_look), ("store_plan", _store_plans_ending), ("store_week", _store_weeks),
        ("win_back", _win_back),
    ):
        if left <= 0:
            break
        out[kind] = await step(db, left)
        left -= out[kind]
    return out


async def lifecycle_forever() -> None:
    """Runs for the life of the API process."""
    from app.db.session import AsyncSessionLocal

    await asyncio.sleep(120)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                result = await run_once(db)
            if any(result.values()):
                logger.info("lifecycle_emails", **result)
        except Exception as exc:  # noqa: BLE001 - never let the loop die (a "slow down" waits for the next round)
            logger.warning("lifecycle_emails_failed", error=str(exc)[:200])
        await asyncio.sleep(RUN_EVERY_SECONDS)
