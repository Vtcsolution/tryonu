"""Team people: community profiles (name, @username, photo) the TryOnU team
posts its Ready looks as. On the community feed such a post looks like any
member's post: the try-on picture with its products. On tryonu.app/looks the
same look shows as the outfit-receipt picture.

A team person is an account that can't sign in (no password, an address
nobody reads) and gets no emails. Any team member can post as any of them.
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.v1.endpoints.community import AVATAR_PREFIX, AVATAR_URL, HANDLE_RE, RESERVED, _remove_old_avatar, _square_avatar
from app.core.deps import DbSession, TeamUser
from app.core.logging import logger
from app.models.community import CommunityPost
from app.models.enums import AuthProvider, JobStatus
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
