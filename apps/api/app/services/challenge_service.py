"""Weekly style challenges: rank the entries, and when a challenge ends pay
its prizes to the most-liked looks (1st, 2nd, 3rd) and tell everyone who
took part. A member's own like on their entry doesn't count, and an entry
needs at least one like to win."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.community import Challenge, ChallengeWinner, CommunityPost, PostLike
from app.models.enums import CreditReason
from app.models.user import User

ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def state(ch: Challenge, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now < _aware(ch.starts_at):
        return "upcoming"
    if now < _aware(ch.ends_at) and ch.finished_at is None:
        return "live"
    return "ended"


def prizes(ch: Challenge) -> list[int]:
    return [ch.prize_1, ch.prize_2, ch.prize_3]


async def ranked_entries(db: AsyncSession, challenge_id: str) -> list[tuple[CommunityPost, int]]:
    """Every visible entry with its likes from other members, best first (ties: the earlier entry)."""
    likes = (
        select(PostLike.post_id.label("post_id"), func.count().label("n"))
        .join(CommunityPost, CommunityPost.id == PostLike.post_id)
        .where(CommunityPost.challenge_id == challenge_id, PostLike.user_id != CommunityPost.user_id)
        .group_by(PostLike.post_id)
        .subquery()
    )
    score = func.coalesce(likes.c.n, 0)
    rows = (
        await db.execute(
            select(CommunityPost, score)
            .join(User, User.id == CommunityPost.user_id)
            .outerjoin(likes, likes.c.post_id == CommunityPost.id)
            .where(
                CommunityPost.challenge_id == challenge_id,
                CommunityPost.is_hidden.is_(False),
                User.community_banned_at.is_(None),
            )
            .order_by(score.desc(), CommunityPost.created_at.asc())
        )
    ).all()
    return [(post, int(n)) for post, n in rows]


async def finish(db: AsyncSession, ch: Challenge) -> list[ChallengeWinner]:
    """Choose and pay the winners (once), and tell everyone who took part."""
    from app.services import credit_service
    from app.services.notification_service import notify

    if ch.finished_at is not None:
        return []
    ranked = await ranked_entries(db, ch.id)
    winners: list[ChallengeWinner] = []
    seen: set[str] = set()
    for post, likes in ranked:
        if len(winners) == 3 or likes < 1:
            break
        if post.user_id in seen:
            continue
        seen.add(post.user_id)
        place = len(winners) + 1
        credits = max(0, prizes(ch)[place - 1] or 0)
        winner = ChallengeWinner(challenge_id=ch.id, user_id=post.user_id, post_id=post.id, place=place, credits=credits, likes=likes)
        db.add(winner)
        winners.append(winner)
        if credits:
            await credit_service.grant(
                db,
                user_id=post.user_id,
                amount=credits,
                reason=CreditReason.CHALLENGE_PRIZE,
                reference_type="challenge",
                reference_id=ch.id,
                note=f"{ORDINAL[place]} place in {ch.title}",
            )
        await notify(
            db, user_id=post.user_id, kind="challenge_win", post_id=post.id, challenge_id=ch.id, credits=credits,
            text=f"{ORDINAL[place]} place in {ch.title}",
        )
    for user_id in {post.user_id for post, _ in ranked} - seen:
        await notify(db, user_id=user_id, kind="challenge_ended", challenge_id=ch.id, text=ch.title)
    ch.finished_at = datetime.now(timezone.utc)
    if _aware(ch.ends_at) > ch.finished_at:  # finished early by an admin
        ch.ends_at = ch.finished_at
    await db.flush()
    return winners


async def finish_due(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    due = (
        await db.execute(
            select(Challenge)
            .where(Challenge.finished_at.is_(None), Challenge.is_hidden.is_(False), Challenge.ends_at <= now)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    for ch in due:
        await finish(db, ch)
    await db.commit()
    return len(due)


CHECK_EVERY_SECONDS = 5 * 60


async def finish_forever() -> None:
    from app.db.session import AsyncSessionLocal

    while True:
        await asyncio.sleep(CHECK_EVERY_SECONDS)
        try:
            async with AsyncSessionLocal() as db:
                done = await finish_due(db)
            if done:
                logger.info("challenges_finished", count=done)
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            logger.warning("challenge_finish_failed", error=str(exc)[:200])
