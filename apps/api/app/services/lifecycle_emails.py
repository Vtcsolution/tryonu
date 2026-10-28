"""The emails the site sends by itself, so nobody has to remember to:

- welcome: once a member confirmed their email, how to get their first look
- first_look: two days later, if they haven't tried anything on yet (with the
  $1 first outfit when they've never bought)
- look_ready: an hour after a finished try-on, a nudge to shop the pieces
  (at most one every three days)
- the weekly trending looks email to every member who gets emails (into the
  Send email queue, so it goes out slowly)

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

RUN_EVERY_SECONDS = 30 * 60
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


async def _send(db: AsyncSession, user: User, kind: str, subject: str, mail: tuple[str, str], ref: str = "") -> bool:
    """Marks it sent first (so a crash never sends twice), then sends."""
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
            to=user.email, subject=subject, text_body=text, html_body=page, unsubscribe_url=unsubscribe_url(user.id)
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


async def run_once(db: AsyncSession) -> dict:
    s = get_settings()
    out = {"welcome": 0, "first_look": 0, "look_ready": 0, "weekly": False}
    if s.WEEKLY_LOOKS_EMAIL_ON:
        out["weekly"] = await _weekly_looks(db)
    if not s.AUTO_EMAILS_ON:
        return out
    left = PER_ROUND
    for kind, step in (("welcome", _welcome), ("first_look", _first_look), ("look_ready", _look_ready)):
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
