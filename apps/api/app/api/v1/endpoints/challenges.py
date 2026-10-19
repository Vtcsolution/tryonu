"""Weekly style challenges: members see the challenge running now, its prizes
and entries (most liked first), and the winners once it ends; admins create,
edit, end and hide challenges (Admin -> Community -> Challenges)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.models.community import Challenge, ChallengeWinner, CommunityPost
from app.models.store import Store
from app.models.user import User
from app.services import challenge_service as svc
from app.services import store_service

from .community import AuthorOut, FeedOut, _author, _posts_out, ensure_handle

router = APIRouter(prefix="/community/challenges", tags=["community"])
admin_router = APIRouter(prefix="/admin/community/challenges", tags=["admin"])


class SponsorOut(BaseModel):
    name: str
    slug: str
    logo_url: str | None


class WinnerOut(BaseModel):
    place: int
    credits: int
    likes: int
    author: AuthorOut
    post_id: str | None


class ChallengeOut(BaseModel):
    id: str
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    state: str  # upcoming | live | ended
    prizes: list[int]
    sponsor: SponsorOut | None
    entries: int
    my_entry_post_id: str | None
    winners: list[WinnerOut]
    hidden: bool = False


async def _out(db: DbSession, ch: Challenge, me: User) -> ChallengeOut:
    sponsor = None
    if ch.sponsor_store_id and (store := await db.get(Store, ch.sponsor_store_id)):
        sponsor = SponsorOut(
            name=store.name, slug=store.slug, logo_url=store_service.image_url(store.logo_key) if store.logo_key else None
        )
    entries = await db.scalar(
        select(func.count()).select_from(CommunityPost).where(CommunityPost.challenge_id == ch.id, CommunityPost.is_hidden.is_(False))
    )
    mine = await db.scalar(select(CommunityPost.id).where(CommunityPost.challenge_id == ch.id, CommunityPost.user_id == me.id))
    winners = [
        WinnerOut(place=w.place, credits=w.credits, likes=w.likes, author=_author(u), post_id=w.post_id)
        for w, u in (
            await db.execute(
                select(ChallengeWinner, User)
                .join(User, User.id == ChallengeWinner.user_id)
                .where(ChallengeWinner.challenge_id == ch.id)
                .order_by(ChallengeWinner.place)
            )
        ).all()
    ]
    return ChallengeOut(
        id=ch.id, title=ch.title, description=ch.description, starts_at=ch.starts_at, ends_at=ch.ends_at, state=svc.state(ch),
        prizes=svc.prizes(ch), sponsor=sponsor, entries=int(entries or 0), my_entry_post_id=mine, winners=winners,
        hidden=ch.is_hidden,
    )


class ChallengesOut(BaseModel):
    live: list[ChallengeOut]
    upcoming: list[ChallengeOut]
    ended: list[ChallengeOut]


@router.get("", response_model=ChallengesOut)
async def list_challenges(me: CurrentUser, db: DbSession):
    """The challenge running now (shown as a banner), what's coming, and recent winners."""
    rows = (
        await db.execute(select(Challenge).where(Challenge.is_hidden.is_(False)).order_by(Challenge.ends_at.desc()).limit(40))
    ).scalars().all()
    out = ChallengesOut(live=[], upcoming=[], ended=[])
    for ch in rows:
        bucket = getattr(out, svc.state(ch))
        if svc.state(ch) == "ended" and len(bucket) >= 10:
            continue
        bucket.append(await _out(db, ch, me))
    out.live.sort(key=lambda c: c.ends_at)
    out.upcoming.sort(key=lambda c: c.starts_at)
    return out


class ChallengeEntriesOut(BaseModel):
    challenge: ChallengeOut
    entries: FeedOut


@router.get("/{challenge_id}", response_model=ChallengeEntriesOut)
async def get_challenge(challenge_id: str, me: CurrentUser, db: DbSession, offset: int = 0, limit: int = 12):
    ch = await db.get(Challenge, challenge_id)
    if ch is None or (ch.is_hidden and not me.is_admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    await ensure_handle(db, me)
    limit = min(max(limit, 1), 30)
    ranked = await svc.ranked_entries(db, ch.id)
    page = ranked[max(offset, 0) : max(offset, 0) + limit]
    posts = await _posts_out(db, [p for p, _ in page], me)
    await db.commit()
    return ChallengeEntriesOut(
        challenge=await _out(db, ch, me),
        entries=FeedOut(posts=posts, next_offset=offset + limit if len(ranked) > offset + limit else None),
    )


# ------------------------------------------------------------------ admin


class ChallengeIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: datetime
    ends_at: datetime
    prize_1: int = Field(default=50, ge=0, le=10000)
    prize_2: int = Field(default=30, ge=0, le=10000)
    prize_3: int = Field(default=20, ge=0, le=10000)
    sponsor_store_slug: str | None = Field(default=None, max_length=140)


async def _apply(db: DbSession, ch: Challenge, payload: ChallengeIn) -> None:
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The end must be after the start.")
    ch.title = payload.title.strip()
    ch.description = (payload.description or "").strip() or None
    ch.starts_at = payload.starts_at if payload.starts_at.tzinfo else payload.starts_at.replace(tzinfo=timezone.utc)
    ch.ends_at = payload.ends_at if payload.ends_at.tzinfo else payload.ends_at.replace(tzinfo=timezone.utc)
    ch.prize_1, ch.prize_2, ch.prize_3 = payload.prize_1, payload.prize_2, payload.prize_3
    ch.sponsor_store_id = None
    if payload.sponsor_store_slug and payload.sponsor_store_slug.strip():
        store = await db.scalar(select(Store).where(Store.slug == payload.sponsor_store_slug.strip().lower()))
        if store is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No store with that link name.")
        ch.sponsor_store_id = store.id


@admin_router.get("", response_model=list[ChallengeOut])
async def admin_list(me: AdminUser, db: DbSession):
    rows = (await db.execute(select(Challenge).order_by(Challenge.starts_at.desc()).limit(100))).scalars().all()
    return [await _out(db, ch, me) for ch in rows]


@admin_router.post("", response_model=ChallengeOut, status_code=status.HTTP_201_CREATED)
async def admin_create(payload: ChallengeIn, me: AdminUser, db: DbSession):
    ch = Challenge(title="", starts_at=payload.starts_at, ends_at=payload.ends_at)
    await _apply(db, ch, payload)
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return await _out(db, ch, me)


@admin_router.put("/{challenge_id}", response_model=ChallengeOut)
async def admin_update(challenge_id: str, payload: ChallengeIn, me: AdminUser, db: DbSession):
    ch = await db.get(Challenge, challenge_id)
    if ch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    if ch.finished_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This challenge has ended and its prizes were given.")
    await _apply(db, ch, payload)
    await db.commit()
    return await _out(db, ch, me)


@admin_router.post("/{challenge_id}/finish", response_model=ChallengeOut)
async def admin_finish(challenge_id: str, me: AdminUser, db: DbSession):
    """End it now: choose and pay the winners."""
    ch = await db.scalar(select(Challenge).where(Challenge.id == challenge_id).with_for_update())
    if ch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    await svc.finish(db, ch)
    await db.commit()
    return await _out(db, ch, me)


class HiddenIn(BaseModel):
    hidden: bool


@admin_router.post("/{challenge_id}/hidden", response_model=ChallengeOut)
async def admin_hide(challenge_id: str, payload: HiddenIn, me: AdminUser, db: DbSession):
    """Hide a challenge (made by mistake): members stop seeing it; its posts stay as normal posts."""
    ch = await db.get(Challenge, challenge_id)
    if ch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")
    ch.is_hidden = payload.hidden
    await db.commit()
    return await _out(db, ch, me)
