"""Notifications: the bell, phone notifications (Web Push) and the daily email.

`notify()` records that something happened to a member. Once the request's
database transaction commits, phones that said yes to notifications get it
at once (when VAPID keys are set); anything still unread a while later goes
into one short daily email (members can turn that off)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import logger
from app.models.notification import Notification, PushSubscription
from app.models.user import User

# the same person liking, unliking and liking again tells the owner once
ONCE_PER_ACTOR = {"post_like", "comment_like", "follow"}
_PENDING = "tryonu_new_notifications"


async def notify(
    db: AsyncSession,
    *,
    user_id: str,
    kind: str,
    actor_id: str | None = None,
    post_id: str | None = None,
    comment_id: str | None = None,
    credits: int | None = None,
    text: str | None = None,
) -> Notification | None:
    if not user_id or (actor_id and actor_id == user_id):
        return None
    if kind in ONCE_PER_ACTOR:
        seen = await db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.kind == kind,
                Notification.actor_id == actor_id,
                Notification.post_id.is_(None) if post_id is None else Notification.post_id == post_id,
                Notification.comment_id.is_(None) if comment_id is None else Notification.comment_id == comment_id,
            )
        )
        if seen is not None:
            return None
    note = Notification(
        user_id=user_id, kind=kind, actor_id=actor_id, post_id=post_id, comment_id=comment_id, credits=credits,
        text=(text or "").strip()[:300] or None,
    )
    db.add(note)
    await db.flush()
    db.sync_session.info.setdefault(_PENDING, []).append(note.id)
    return note


def snippet(body: str | None, limit: int = 90) -> str | None:
    body = " ".join((body or "").split())
    if not body:
        return None
    return body if len(body) <= limit else body[: limit - 1].rstrip() + "…"


# ------------------------------------------------------------------ words and links


def actor_name(actor: User | None) -> str:
    if actor is None:
        return "Someone"
    return actor.full_name or (f"@{actor.handle}" if actor.handle else "A friend")


def words(n: Notification, actor: User | None) -> str:
    who = actor_name(actor)
    quote = f": “{n.text}”" if n.text else ""
    if n.kind == "post_like":
        return f"{who} liked your post"
    if n.kind == "comment":
        return f"{who} commented on your post{quote}"
    if n.kind == "reply":
        return f"{who} replied to your comment{quote}"
    if n.kind == "comment_like":
        return f"{who} liked your comment"
    if n.kind == "follow":
        return f"{who} started following you"
    if n.kind == "referral_joined":
        return f"{who} joined TryOnU from your link"
    if n.kind == "reward":
        return f"You earned {n.credits or 0} free credits" + (f": {n.text}" if n.text else "")
    if n.kind == "credits_added":
        return f"{n.credits or 0} credits were added to your account" + (f" ({n.text})" if n.text else "")
    return n.text or "Something new on TryOnU"


def link(n: Notification, actor: User | None) -> str:
    if n.post_id:
        return f"/community/post/{n.post_id}"
    if n.kind == "follow" and actor is not None and actor.handle:
        return f"/u/{actor.handle}"
    if n.kind in ("referral_joined", "reward"):
        return "/earn"
    if n.kind == "credits_added":
        return "/credits"
    return "/notifications"


# ------------------------------------------------------------------ phone notifications (Web Push)


def push_ready() -> bool:
    s = get_settings()
    return bool(s.VAPID_PUBLIC_KEY and s.VAPID_PRIVATE_KEY)


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    ids = session.info.pop(_PENDING, None)
    if not ids or not push_ready():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(send_pushes(list(ids)))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_PENDING, None)


_TASKS: set[asyncio.Task] = set()


@dataclass
class _Push:
    sub_id: str
    endpoint: str
    keys: dict
    payload: str


def _send_one(push: _Push) -> int:
    """0 when delivered, else the push service's HTTP status (404/410: that phone is gone)."""
    from pywebpush import WebPushException, webpush

    s = get_settings()
    try:
        webpush(
            subscription_info={"endpoint": push.endpoint, "keys": push.keys},
            data=push.payload,
            vapid_private_key=s.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": s.VAPID_SUBJECT},
            ttl=24 * 3600,
            timeout=10,
        )
        return 0
    except WebPushException as exc:
        return exc.response.status_code if exc.response is not None else 500


async def send_pushes(ids: list[str]) -> int:
    """Each new notification to every phone of its member that said yes."""
    from app.db.session import AsyncSessionLocal

    sent = 0
    async with AsyncSessionLocal() as db:
        notes = (await db.execute(select(Notification).where(Notification.id.in_(ids), Notification.pushed_at.is_(None)))).scalars().all()
        if not notes:
            return 0
        subs: dict[str, list[PushSubscription]] = {}
        for sub in (await db.execute(select(PushSubscription).where(PushSubscription.user_id.in_({n.user_id for n in notes})))).scalars():
            subs.setdefault(sub.user_id, []).append(sub)
        actors = {
            u.id: u
            for u in (await db.execute(select(User).where(User.id.in_({n.actor_id for n in notes if n.actor_id})))).scalars()
        }
        gone: set[str] = set()
        now = datetime.now(timezone.utc)
        for n in notes:
            n.pushed_at = now
            actor = actors.get(n.actor_id) if n.actor_id else None
            payload = json.dumps({"title": "TryOnU", "body": words(n, actor), "url": link(n, actor), "tag": n.id})
            for sub in subs.get(n.user_id, []):
                if sub.id in gone:
                    continue
                status = await asyncio.to_thread(_send_one, _Push(sub.id, sub.endpoint, {"p256dh": sub.p256dh, "auth": sub.auth}, payload))
                if status == 0:
                    sub.last_sent_at = now
                    sent += 1
                elif status in (404, 410):
                    gone.add(sub.id)
                else:
                    logger.warning("push_failed", status=status, subscription_id=sub.id)
        for sub_id in gone:
            sub = await db.get(PushSubscription, sub_id)
            if sub is not None:
                await db.delete(sub)
        await db.commit()
    return sent


# ------------------------------------------------------------------ the daily email


def unsubscribe_token(user_id: str) -> str:
    key = get_settings().SECRET_KEY.encode()
    return hmac.new(key, f"notify-email:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def unsubscribe_url(user_id: str) -> str:
    api = get_settings().PUBLIC_API_BASE_URL.rstrip("/")
    return f"{api}/api/v1/notifications/unsubscribe?u={user_id}&t={unsubscribe_token(user_id)}"


async def send_digests(db: AsyncSession, *, max_members: int = 300) -> int:
    """One short email to each member with unread news (older than an hour,
    so the bell and phone had their chance), at most once a day."""
    from app.email.registry import get_email_provider

    s = get_settings()
    now = datetime.now(timezone.utc)
    settle = now - timedelta(hours=1)
    since = now - timedelta(hours=s.NOTIFY_DIGEST_HOURS)
    waiting = (
        select(Notification.user_id)
        .where(Notification.read_at.is_(None), Notification.emailed_at.is_(None), Notification.created_at <= settle)
        .distinct()
    )
    members = (
        await db.execute(
            select(User)
            .where(
                User.id.in_(waiting),
                User.notify_email.is_(True),
                User.is_active.is_(True),
                (User.notify_digest_at.is_(None)) | (User.notify_digest_at <= since),
            )
            .limit(max_members)
        )
    ).scalars().all()
    site = str(s.FRONTEND_URL).rstrip("/")
    sent = 0
    for member in members:
        notes = (
            await db.execute(
                select(Notification)
                .where(Notification.user_id == member.id, Notification.read_at.is_(None), Notification.emailed_at.is_(None))
                .order_by(Notification.created_at.desc())
            )
        ).scalars().all()
        if not notes:
            continue
        actors = {
            u.id: u
            for u in (await db.execute(select(User).where(User.id.in_({n.actor_id for n in notes if n.actor_id})))).scalars()
        }
        lines = [f"• {words(n, actors.get(n.actor_id))}" for n in notes[:6]]
        if len(notes) > 6:
            lines.append(f"…and {len(notes) - 6} more")
        hello = f"Hi {member.full_name.split()[0]}," if member.full_name else "Hi,"
        subject = f"You have {len(notes)} new {'notification' if len(notes) == 1 else 'notifications'} on TryOnU"
        body = (
            f"{hello}\n\nHere is what happened on TryOnU:\n\n" + "\n".join(lines)
            + f"\n\nSee them all: {site}/notifications\n\n"
            + f"Don't want these emails? Turn them off here: {unsubscribe_url(member.id)}\n\nTryOnU"
        )
        try:
            await get_email_provider().send(to=member.email, subject=subject, text_body=body)
        except Exception as exc:  # noqa: BLE001 — try again next round
            logger.warning("digest_email_failed", user_id=member.id, error=str(exc)[:200])
            continue
        await db.execute(update(Notification).where(Notification.id.in_([n.id for n in notes])).values(emailed_at=now))
        member.notify_digest_at = now
        sent += 1
    await db.commit()
    return sent


DIGEST_EVERY_SECONDS = 30 * 60


async def digest_forever() -> None:
    from app.db.session import AsyncSessionLocal

    while True:
        await asyncio.sleep(DIGEST_EVERY_SECONDS)
        try:
            async with AsyncSessionLocal() as db:
                sent = await send_digests(db)
            if sent:
                logger.info("notification_digests_sent", count=sent)
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            logger.warning("notification_digest_failed", error=str(exc)[:200])
