"""The team panel's people and history.

Team people: community profiles (name, @username, photo) the TryOnU team
posts its Ready looks as. On the community feed such a post looks like any
member's post: the try-on picture with its products. On tryonu.app/looks the
same look shows as the outfit-receipt picture.

A team person is an account that can't sign in (no password, an address
nobody reads) and gets no emails. Any team member can post as any of them.

History: every try-on the team member made, finished or failed, with what
happened to the credits.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.community import AVATAR_PREFIX, AVATAR_URL, HANDLE_RE, RESERVED, _remove_old_avatar, _square_avatar
from app.core.deps import DbSession, TeamUser
from app.core.logging import logger
from app.models.community import CommunityPost
from app.models.credit import CreditTransaction
from app.models.enums import AuthProvider, CreditReason, JobStatus
from app.models.outfit import Outfit
from app.models.ready_look import ReadyLook
from app.models.tryon import TryOnJob
from app.models.user import User
from app.services.community_links import clean_text
from app.services.storage_service import get_storage

router = APIRouter(prefix="/team", tags=["team people"])

MAX_PHOTO = 15 * 1024 * 1024


class PersonOut(BaseModel):
    id: str
    name: str
    handle: str
    avatar_url: str | None
    posts: int


class CommunityPostIn(BaseModel):
    person_id: str
    caption: str | None = Field(default=None, max_length=1000)
    poll: bool = False  # ask the community: Buy or skip?


class CommunityPostOut(BaseModel):
    post_id: str
    handle: str


def _clean_handle(raw: str) -> str:
    handle = raw.strip().lower().lstrip("@")
    if not HANDLE_RE.match(handle) or handle in RESERVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A username is 3–30 letters, numbers, dots or underscores.")
    return handle


async def _handle_free(db: DbSession, handle: str, user_id: str | None = None) -> None:
    taken = await db.scalar(select(User.id).where(User.handle == handle, User.id != (user_id or "")))
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That username is taken. Try another one.")


async def _set_photo(user: User, photo: UploadFile) -> None:
    raw = await photo.read()
    if len(raw) > MAX_PHOTO:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="That photo is too big. Please use one under 15 MB.")
    content = _square_avatar(raw)
    name = f"{user.id}-{secrets.token_urlsafe(8)}.jpg"
    get_storage().put(AVATAR_PREFIX + name, content, "image/jpeg")
    _remove_old_avatar(user)
    user.avatar_url = AVATAR_URL + name


async def _person(db: DbSession, person_id: str) -> User:
    person = await db.get(User, person_id)
    if person is None or not person.team_person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


async def _out(db: DbSession, people: list[User]) -> list[PersonOut]:
    counts = dict(
        (
            await db.execute(
                select(CommunityPost.user_id, func.count())
                .where(CommunityPost.user_id.in_([p.id for p in people] or [""]))
                .group_by(CommunityPost.user_id)
            )
        ).all()
    )
    return [
        PersonOut(id=p.id, name=p.full_name or p.handle or "", handle=p.handle or "", avatar_url=p.avatar_url, posts=counts.get(p.id, 0))
        for p in people
    ]


@router.get("/people", response_model=list[PersonOut])
async def list_people(_: TeamUser, db: DbSession):
    people = list((await db.execute(select(User).where(User.team_person.is_(True)).order_by(User.full_name))).scalars())
    return await _out(db, people)


@router.post("/people", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def add_person(
    me: TeamUser,
    db: DbSession,
    name: str = Form(..., min_length=2, max_length=60),
    handle: str = Form(...),
    photo: UploadFile = File(...),
):
    handle = _clean_handle(handle)
    await _handle_free(db, handle)
    person = User(
        email=f"person.{uuid.uuid4().hex[:16]}@people.tryonu.app",
        full_name=name.strip(),
        handle=handle,
        auth_provider=AuthProvider.LOCAL,
        hashed_password=None,
        email_verified=False,
        notify_email=False,
        team_person=True,
    )
    db.add(person)
    await db.flush()
    await _set_photo(person, photo)
    await db.commit()
    logger.info("team_person_added", person_id=person.id, by=me.id)
    return (await _out(db, [person]))[0]


@router.patch("/people/{person_id}", response_model=PersonOut)
async def edit_person(
    person_id: str,
    _: TeamUser,
    db: DbSession,
    name: str | None = Form(default=None, max_length=60),
    handle: str | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
):
    person = await _person(db, person_id)
    if name and name.strip():
        person.full_name = name.strip()
    if handle:
        new = _clean_handle(handle)
        await _handle_free(db, new, person.id)
        person.handle = new
    if photo is not None:
        await _set_photo(person, photo)
    await db.commit()
    return (await _out(db, [person]))[0]


@router.post("/looks/{look_id}/community", response_model=CommunityPostOut, status_code=status.HTTP_201_CREATED)
async def post_to_community(look_id: str, payload: CommunityPostIn, me: TeamUser, db: DbSession):
    """The look's try-on goes on the community feed as this person, with the
    look's products under it, like a member's own post."""
    look = await db.get(ReadyLook, look_id)
    if look is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Look not found")
    job = await db.get(TryOnJob, look.tryon_job_id) if look.tryon_job_id else None
    if job is None or job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This look has no try-on to post. Only looks made with Try on can go to the community.",
        )
    person = await _person(db, payload.person_id)
    already = await db.scalar(select(CommunityPost.id).where(CommunityPost.user_id == person.id, CommunityPost.tryon_job_id == job.id))
    if already is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"@{person.handle} has already posted this look.")
    caption, removed = clean_text(payload.caption)
    post = CommunityPost(user_id=person.id, tryon_job_id=job.id, caption=caption or None, links_removed=removed, poll=payload.poll)
    db.add(post)
    await db.commit()
    logger.info("team_community_post", look_id=look.id, person_id=person.id, post_id=post.id, by=me.id)
    return CommunityPostOut(post_id=post.id, handle=person.handle or "")


# ------------------------------------------------------------------ try-on history


class TeamTryOnOut(BaseModel):
    id: str
    status: str  # done | failed | working
    what: str
    items: int
    image_url: str | None  # the result, or the photo it started from
    error: str | None
    credits: int
    refunded: bool  # a failed try-on's credits came back
    look_id: str | None  # the Ready look made from it
    community: list[CommunityPostOut] = []  # its posts on the community feed
    created_at: datetime


class TeamTryOnsOut(BaseModel):
    items: list[TeamTryOnOut]
    total: int
    done: int
    failed: int
    working: int
    next_offset: int | None


_STATE = {
    JobStatus.COMPLETED: "done",
    JobStatus.FAILED: "failed",
    JobStatus.CANCELLED: "failed",
    JobStatus.QUEUED: "working",
    JobStatus.PROCESSING: "working",
}
_SHOW = {
    "done": [JobStatus.COMPLETED],
    "failed": [JobStatus.FAILED, JobStatus.CANCELLED],
    "working": [JobStatus.QUEUED, JobStatus.PROCESSING],
}


@router.get("/tryons", response_model=TeamTryOnsOut)
async def my_tryons(
    me: TeamUser,
    db: DbSession,
    show: str | None = Query(default=None, pattern="^(done|failed|working)$"),
    limit: int = Query(default=24, ge=1, le=60),
    offset: int = Query(default=0, ge=0),
):
    """Every try-on this team member made, newest first: finished, failed or still working."""
    counts = dict(
        (await db.execute(select(TryOnJob.status, func.count()).where(TryOnJob.user_id == me.id).group_by(TryOnJob.status))).all()
    )
    tally = {"done": 0, "failed": 0, "working": 0}
    for st, n in counts.items():
        tally[_STATE.get(JobStatus(st), "failed")] += n
    query = select(TryOnJob).where(TryOnJob.user_id == me.id)
    if show:
        query = query.where(TryOnJob.status.in_(_SHOW[show]))
    jobs = list(
        (
            await db.execute(
                query.options(
                    selectinload(TryOnJob.result),
                    selectinload(TryOnJob.user_photo),
                    selectinload(TryOnJob.product),
                    selectinload(TryOnJob.wardrobe_item),
                    selectinload(TryOnJob.outfit).selectinload(Outfit.items),
                )
                .order_by(TryOnJob.created_at.desc())
                .limit(limit + 1)
                .offset(offset)
            )
        ).scalars()
    )
    more = len(jobs) > limit
    jobs = jobs[:limit]
    ids = [j.id for j in jobs] or [""]
    refunded = set(
        (
            await db.execute(
                select(CreditTransaction.reference_id).where(
                    CreditTransaction.reason == CreditReason.TRYON_REFUND,
                    CreditTransaction.reference_type == "tryon_job",
                    CreditTransaction.reference_id.in_(ids),
                )
            )
        ).scalars()
    )
    looks = dict((await db.execute(select(ReadyLook.tryon_job_id, ReadyLook.id).where(ReadyLook.tryon_job_id.in_(ids)))).all())
    posted: dict[str, list[CommunityPostOut]] = {}
    for job_id, post_id, handle in (
        await db.execute(
            select(CommunityPost.tryon_job_id, CommunityPost.id, User.handle)
            .join(User, User.id == CommunityPost.user_id)
            .where(CommunityPost.tryon_job_id.in_(ids), CommunityPost.is_hidden.is_(False))
        )
    ).all():
        posted.setdefault(job_id, []).append(CommunityPostOut(post_id=post_id, handle=handle or "member"))
    storage = get_storage()
    items = []
    for j in jobs:
        if j.outfit is not None:
            what, count = j.outfit.name or "Outfit", len(j.outfit.items)
        elif j.product is not None:
            what, count = j.product.name, 1
        elif j.wardrobe_item is not None:
            what, count = j.wardrobe_item.name, 1
        else:
            what, count = "Try-on", 0
        if j.look_round > 1:
            what = f"{what} (added to a look)"
        key = j.result.storage_key if j.result is not None else (j.user_photo.storage_key if j.user_photo else None)
        state = _STATE.get(j.status, "failed")
        items.append(
            TeamTryOnOut(
                id=j.id,
                status=state,
                what=what,
                items=count,
                image_url=storage.signed_url(key) if key else None,
                error=(j.error_message or "It didn't work this time.") if state == "failed" else None,
                credits=j.credit_cost,
                refunded=j.id in refunded,
                look_id=looks.get(j.id),
                community=posted.get(j.id, []),
                created_at=j.created_at,
            )
        )
    return TeamTryOnsOut(
        items=items,
        total=sum(tally.values()),
        next_offset=offset + limit if more else None,
        **tally,
    )
