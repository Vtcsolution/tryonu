"""The TryOnU community (signed-in members only).

Members post finished looks, photos and videos with a caption; others like
them, comment (replies to replies, like Facebook; a comment can carry a photo
or one of the member's own looks, and can be liked), follow the people whose
style they like, and press "Try this look" to put the same products on their
own photo. Only TryOnU links (stores, products, looks, posts) may be shared:
any other link is taken out before it is saved. Anyone can report a post or
comment; admins see every member's activity and every comment, and hide
content or block a member (Admin -> Community)."""

from __future__ import annotations

import math
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.community import CommentLike, CommunityPost, CommunityReport, Follow, PostComment, PostLike
from app.models.enums import JobStatus
from app.models.tryon import TryOnJob
from app.models.user import User
from app.services.community_links import LinkPreviewOut, clean_text, previews
from app.services.look_products import copy_look, look_products
from app.services.storage_service import get_storage

router = APIRouter(prefix="/community", tags=["community"])
admin_router = APIRouter(prefix="/admin/community", tags=["admin"])

HANDLE_RE = re.compile(r"^[a-z0-9_.]{3,30}$")
RESERVED = {"admin", "tryonu", "support", "help", "official", "team", "moderator", "staff", "root", "system"}


# ------------------------------------------------------------------ people


async def ensure_handle(db: DbSession, user: User) -> str:
    """Every member gets an @handle the first time they use the community."""
    if user.handle:
        return user.handle
    base = re.sub(r"[^a-z0-9]+", "", (user.full_name or user.email.split("@")[0]).lower())[:20] or "member"
    if len(base) < 3:
        base = f"{base}style"
    candidate = base
    while candidate in RESERVED or await db.scalar(select(User.id).where(User.handle == candidate)) is not None:
        candidate = f"{base}{secrets.randbelow(9000) + 1000}"
    user.handle = candidate
    await db.flush()
    return candidate


class AuthorOut(BaseModel):
    handle: str
    name: str | None
    avatar_url: str | None


def _author(u: User) -> AuthorOut:
    return AuthorOut(handle=u.handle or "member", name=u.full_name, avatar_url=u.avatar_url)


def _can_write(user: User) -> None:
    if user.community_banned_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't post or comment in the community.")


# ------------------------------------------------------------------ posts


class LookProductOut(BaseModel):
    id: str
    name: str
    price_cents: int
    currency: str
    image_url: str | None
    shop: str | None
    buy_url: str


class PostOut(BaseModel):
    id: str
    author: AuthorOut
    media_kind: str = "tryon"  # tryon | image | video
    image_url: str | None
    video_url: str | None = None
    poster_url: str | None = None
    caption: str | None
    like_count: int
    comment_count: int
    liked_by_me: bool
    following_author: bool
    is_mine: bool
    products: list[LookProductOut]
    created_at: datetime
    # a few of the people who liked it, newest first (the small faces by the counts)
    likers: list[AuthorOut] = []
    previews: list[LinkPreviewOut] = []
    links_removed: int = 0  # only on the answer to the one who just posted it


async def _recent_likers(db: DbSession, post_ids: list[str], per_post: int = 3) -> dict[str, list[AuthorOut]]:
    if not post_ids:
        return {}
    rank = func.row_number().over(partition_by=PostLike.post_id, order_by=PostLike.created_at.desc()).label("rank")
    inner = select(PostLike.post_id, PostLike.user_id, rank).where(PostLike.post_id.in_(post_ids)).subquery()
    rows = (
        await db.execute(
            select(inner.c.post_id, User)
            .join(User, User.id == inner.c.user_id)
            .where(inner.c.rank <= per_post)
            .order_by(inner.c.post_id, inner.c.rank)
        )
    ).all()
    out: dict[str, list[AuthorOut]] = {}
    for post_id, user in rows:
        out.setdefault(post_id, []).append(_author(user))
    return out


async def _posts_out(db: DbSession, posts: list[CommunityPost], me: User) -> list[PostOut]:
    if not posts:
        return []
    ids = [p.id for p in posts]
    authors = {u.id: u for u in (await db.execute(select(User).where(User.id.in_({p.user_id for p in posts})))).scalars()}
    liked = set((await db.execute(select(PostLike.post_id).where(PostLike.user_id == me.id, PostLike.post_id.in_(ids)))).scalars())
    following = set(
        (await db.execute(select(Follow.followee_id).where(Follow.follower_id == me.id, Follow.followee_id.in_(authors.keys())))).scalars()
    )
    job_ids = [p.tryon_job_id for p in posts if p.tryon_job_id]
    jobs = (
        {
            j.id: j
            for j in (
                await db.execute(select(TryOnJob).where(TryOnJob.id.in_(job_ids)).options(selectinload(TryOnJob.result)))
            ).scalars()
        }
        if job_ids
        else {}
    )
    storage = get_storage()
    api = get_settings().PUBLIC_API_BASE_URL.rstrip("/")
    likers = await _recent_likers(db, ids)
    out: list[PostOut] = []
    for p in posts:
        extra = {"likers": likers.get(p.id, []), "previews": await previews(db, p.caption)}
        if p.media_key:  # a photo or video the member uploaded
            out.append(
                PostOut(
                    id=p.id,
                    author=_author(authors[p.user_id]),
                    media_kind=p.media_kind,
                    image_url=storage.signed_url(p.media_key) if p.media_kind == "image" else None,
                    video_url=storage.signed_url(p.media_key) if p.media_kind == "video" else None,
                    poster_url=storage.signed_url(p.poster_key) if p.poster_key else None,
                    caption=p.caption,
                    like_count=p.like_count,
                    comment_count=p.comment_count,
                    liked_by_me=p.id in liked,
                    following_author=p.user_id in following,
                    is_mine=p.user_id == me.id,
                    products=[],
                    created_at=p.created_at,
                    **extra,
                )
            )
            continue
        job = jobs.get(p.tryon_job_id)
        if job is None or job.result is None:
            continue
        pairs, _ = await look_products(db, job)
        out.append(
            PostOut(
                id=p.id,
                author=_author(authors[p.user_id]),
                # a fresh signed link each time: stored links expire
                image_url=storage.signed_url(job.result.storage_key),
                caption=p.caption,
                like_count=p.like_count,
                comment_count=p.comment_count,
                liked_by_me=p.id in liked,
                following_author=p.user_id in following,
                is_mine=p.user_id == me.id,
                products=[
                    LookProductOut(
                        id=prod.id,
                        name=prod.name,
                        price_cents=prod.price_cents,
                        currency=prod.currency,
                        image_url=prod.primary_image_url,
                        shop=prod.merchant_name or (prod.retailer.name if prod.retailer else None),
                        buy_url=f"{api}/api/v1/affiliate/go/{prod.id}?source=community",
                    )
                    for prod, _ in pairs
                ],
                created_at=p.created_at,
                **extra,
            )
        )
    return out


def _visible():
    """Posts anyone may see: not hidden, and not from a blocked member."""
    return (CommunityPost.is_hidden.is_(False)) & (User.community_banned_at.is_(None))


class FeedOut(BaseModel):
    posts: list[PostOut]
    next_offset: int | None


@router.get("/feed", response_model=FeedOut)
async def feed(me: CurrentUser, db: DbSession, tab: str = "for_you", offset: int = 0, limit: int = 12):
    limit = min(max(limit, 1), 30)
    offset = max(offset, 0)
    base = select(CommunityPost).join(User, User.id == CommunityPost.user_id).where(_visible())
    if tab == "following":
        followees = select(Follow.followee_id).where(Follow.follower_id == me.id)
        rows = (
            await db.execute(
                base.where(CommunityPost.user_id.in_(followees)).order_by(CommunityPost.created_at.desc()).offset(offset).limit(limit + 1)
            )
        ).scalars().all()
    else:
        # "For you": recent looks, the ones people like and talk about first
        recent = (await db.execute(base.order_by(CommunityPost.created_at.desc()).limit(500))).scalars().all()
        now = datetime.now(timezone.utc)

        def score(p: CommunityPost) -> float:
            created = p.created_at if p.created_at.tzinfo else p.created_at.replace(tzinfo=timezone.utc)
            hours = max((now - created).total_seconds() / 3600, 0)
            return (1 + p.like_count + 2 * p.comment_count) / math.pow(hours + 2, 1.3)

        rows = sorted(recent, key=score, reverse=True)[offset : offset + limit + 1]
    await ensure_handle(db, me)
    out = await _posts_out(db, list(rows[:limit]), me)
    await db.commit()
    return FeedOut(posts=out, next_offset=offset + limit if len(rows) > limit else None)


class NewPostIn(BaseModel):
    tryon_job_id: str
    caption: str | None = Field(default=None, max_length=1000)
    accept_rules: bool = False


@router.post(
    "/posts",
    response_model=PostOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("community_post", limit=20, window_seconds=3600))],
)
async def create_post(payload: NewPostIn, me: CurrentUser, db: DbSession):
    _can_write(me)
    if not payload.accept_rules:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please agree to the community rules to post.")
    job = await db.scalar(select(TryOnJob).where(TryOnJob.id == payload.tryon_job_id).options(selectinload(TryOnJob.result)))
    if job is None or job.user_id != me.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Look not found")
    if job.status != JobStatus.COMPLETED or job.result is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a finished look can be posted.")
    existing = await db.scalar(select(CommunityPost).where(CommunityPost.user_id == me.id, CommunityPost.tryon_job_id == job.id))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You've already posted this look.")
    await ensure_handle(db, me)
    caption, removed = clean_text(payload.caption)
    post = CommunityPost(user_id=me.id, tryon_job_id=job.id, caption=caption or None, links_removed=removed)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    out = (await _posts_out(db, [post], me))[0]
    out.links_removed = removed
    return out


class MyLookOut(BaseModel):
    job_id: str
    image_url: str
    saved: bool
    post_id: str | None
    created_at: datetime


@router.get("/my-looks", response_model=list[MyLookOut])
async def my_looks(me: CurrentUser, db: DbSession, limit: int = 30):
    """My finished looks to choose from on the community page: saved ones first,
    with the ones already posted marked."""
    from app.models.developer import DeveloperTryOn
    from app.models.outfit import SavedLook

    jobs = (
        await db.execute(
            select(TryOnJob)
            .where(
                TryOnJob.user_id == me.id,
                TryOnJob.status == JobStatus.COMPLETED,
                TryOnJob.id.notin_(select(DeveloperTryOn.tryon_job_id)),  # not try-ons made for API customers
            )
            .options(selectinload(TryOnJob.result))
            .order_by(TryOnJob.created_at.desc())
            .limit(min(max(limit, 1), 60))
        )
    ).scalars().all()
    jobs = [j for j in jobs if j.result is not None]
    if not jobs:
        return []
    saved = set(
        (await db.execute(select(SavedLook.tryon_result_id).where(SavedLook.user_id == me.id))).scalars()
    )
    posted = dict(
        (
            await db.execute(
                select(CommunityPost.tryon_job_id, CommunityPost.id).where(
                    CommunityPost.user_id == me.id, CommunityPost.tryon_job_id.in_([j.id for j in jobs])
                )
            )
        ).all()
    )
    storage = get_storage()
    out = [
        MyLookOut(
            job_id=j.id,
            image_url=storage.signed_url(j.result.storage_key),
            saved=j.result.id in saved,
            post_id=posted.get(j.id),
            created_at=j.created_at,
        )
        for j in jobs
    ]
    return sorted(out, key=lambda x: (not x.saved, -x.created_at.timestamp()))


@router.post(
    "/posts/media",
    response_model=PostOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("community_media", limit=15, window_seconds=3600))],
)
async def create_media_post(
    me: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None, max_length=1000),
    accept_rules: bool = Form(default=False),
):
    """A member posts their own photo or video (videos: up to 60 seconds)."""
    from app.services import community_media

    _can_write(me)
    if not accept_rules:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please agree to the community rules to post.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please choose a photo or video.")
    if community_media.video_kind(raw) is not None:
        key, poster, width, height = await community_media.save_video(me.id, raw)
        kind = "video"
    else:
        key, width, height = await community_media.save_image(me.id, raw)
        poster, kind = None, "image"
    await ensure_handle(db, me)
    text, removed = clean_text(caption)
    post = CommunityPost(
        user_id=me.id, media_kind=kind, media_key=key, poster_key=poster, media_width=width, media_height=height,
        caption=text or None, links_removed=removed,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    out = (await _posts_out(db, [post], me))[0]
    out.links_removed = removed
    return out


@router.get("/posts/by-job/{job_id}")
async def post_for_job(job_id: str, me: CurrentUser, db: DbSession):
    """Is this look of mine already in the community?"""
    post_id = await db.scalar(select(CommunityPost.id).where(CommunityPost.user_id == me.id, CommunityPost.tryon_job_id == job_id))
    return {"post_id": post_id}


async def _visible_post(db: DbSession, post_id: str, me: User) -> CommunityPost:
    post = await db.get(CommunityPost, post_id)
    if post is None or (post.is_hidden and post.user_id != me.id and not me.is_admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@router.get("/posts/{post_id}", response_model=PostOut)
async def get_post(post_id: str, me: CurrentUser, db: DbSession):
    post = await _visible_post(db, post_id, me)
    out = await _posts_out(db, [post], me)
    if not out:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return out[0]


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: str, me: CurrentUser, db: DbSession):
    post = await db.get(CommunityPost, post_id)
    if post is None or (post.user_id != me.id and not me.is_admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    media = (post.media_key, post.poster_key)
    await db.delete(post)
    await db.commit()
    from app.services.community_media import delete_files

    delete_files(*media)


async def _recount_likes(db: DbSession, post: CommunityPost) -> None:
    post.like_count = int(await db.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post.id)) or 0)


@router.post("/posts/{post_id}/like", dependencies=[Depends(rate_limiter("community_like", limit=400, window_seconds=3600))])
async def like_post(post_id: str, me: CurrentUser, db: DbSession):
    _can_write(me)
    post = await _visible_post(db, post_id, me)
    if await db.scalar(select(PostLike.id).where(PostLike.post_id == post.id, PostLike.user_id == me.id)) is None:
        db.add(PostLike(post_id=post.id, user_id=me.id))
        await db.flush()
    await _recount_likes(db, post)
    await db.commit()
    return {"liked": True, "like_count": post.like_count}


@router.delete("/posts/{post_id}/like")
async def unlike_post(post_id: str, me: CurrentUser, db: DbSession):
    post = await _visible_post(db, post_id, me)
    await db.execute(delete(PostLike).where(PostLike.post_id == post.id, PostLike.user_id == me.id))
    await _recount_likes(db, post)
    await db.commit()
    return {"liked": False, "like_count": post.like_count}


@router.get("/posts/{post_id}/likes", response_model=list[AuthorOut])
async def post_likers(post_id: str, me: CurrentUser, db: DbSession):
    """Who liked a post, newest first."""
    post = await _visible_post(db, post_id, me)
    rows = (
        await db.execute(
            select(User)
            .join(PostLike, PostLike.user_id == User.id)
            .where(PostLike.post_id == post.id, User.community_banned_at.is_(None))
            .order_by(PostLike.created_at.desc())
            .limit(300)
        )
    ).scalars()
    return [_author(u) for u in rows]


class TryThisOut(BaseModel):
    outfit_id: str | None = None
    product_id: str | None = None


@router.post("/posts/{post_id}/try", response_model=TryThisOut)
async def try_post_look(post_id: str, me: CurrentUser, db: DbSession):
    """The same products, ready to try on with my own photo."""
    post = await _visible_post(db, post_id, me)
    if not post.tryon_job_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This post has no products to try on.")
    job = await db.scalar(select(TryOnJob).where(TryOnJob.id == post.tryon_job_id).options(selectinload(TryOnJob.result)))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    outfit_id, product_id = await copy_look(db, me.id, job, include_hidden=True)
    if outfit_id is None and product_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The products in this look aren't available anymore.")
    return TryThisOut(outfit_id=outfit_id, product_id=product_id)


# ------------------------------------------------------------------ comments


class CommentLookOut(BaseModel):
    image_url: str
    products: list[LookProductOut]


class CommentOut(BaseModel):
    id: str
    author: AuthorOut
    body: str
    parent_id: str | None
    reply_to: str | None = None  # the @handle this answers (shown on deep replies)
    is_mine: bool
    can_delete: bool
    created_at: datetime
    like_count: int = 0
    liked_by_me: bool = False
    image_url: str | None = None
    look: CommentLookOut | None = None
    previews: list[LinkPreviewOut] = []
    links_removed: int = 0  # only on the answer to the one who just wrote it
    replies: list["CommentOut"] = []


class NewCommentIn(BaseModel):
    body: str = Field(default="", max_length=1000)
    parent_id: str | None = None
    image_key: str | None = Field(default=None, max_length=512)  # from POST /community/comment-images
    tryon_job_id: str | None = None  # one of my own finished looks


async def _recount_comments(db: DbSession, post: CommunityPost) -> None:
    post.comment_count = int(
        await db.scalar(
            select(func.count()).select_from(PostComment).where(PostComment.post_id == post.id, PostComment.is_hidden.is_(False))
        )
        or 0
    )


def _product_out(prod) -> LookProductOut:  # noqa: ANN001
    api = get_settings().PUBLIC_API_BASE_URL.rstrip("/")
    return LookProductOut(
        id=prod.id,
        name=prod.name,
        price_cents=prod.price_cents,
        currency=prod.currency,
        image_url=prod.primary_image_url,
        shop=prod.merchant_name or (prod.retailer.name if prod.retailer else None),
        buy_url=f"{api}/api/v1/affiliate/go/{prod.id}?source=community",
    )


async def _comments_out(
    db: DbSession, rows: list[tuple[PostComment, User]], me: User, post_owner_id: str
) -> dict[str, CommentOut]:
    """Each comment ready to show (without its replies), by id."""
    if not rows:
        return {}
    ids = [c.id for c, _ in rows]
    liked = set(
        (await db.execute(select(CommentLike.comment_id).where(CommentLike.user_id == me.id, CommentLike.comment_id.in_(ids)))).scalars()
    )
    job_ids = [c.tryon_job_id for c, _ in rows if c.tryon_job_id]
    jobs = (
        {
            j.id: j
            for j in (await db.execute(select(TryOnJob).where(TryOnJob.id.in_(job_ids)).options(selectinload(TryOnJob.result)))).scalars()
        }
        if job_ids
        else {}
    )
    handles = {c.id: u.handle or "member" for c, u in rows}
    storage = get_storage()
    out: dict[str, CommentOut] = {}
    for c, u in rows:
        look = None
        job = jobs.get(c.tryon_job_id) if c.tryon_job_id else None
        if job is not None and job.result is not None:
            pairs, _ = await look_products(db, job)
            look = CommentLookOut(image_url=storage.signed_url(job.result.storage_key), products=[_product_out(p) for p, _ in pairs])
        out[c.id] = CommentOut(
            id=c.id,
            author=_author(u),
            body=c.body,
            parent_id=c.parent_id,
            reply_to=handles.get(c.parent_id) if c.parent_id else None,
            is_mine=c.user_id == me.id,
            can_delete=c.user_id == me.id or post_owner_id == me.id or me.is_admin,
            created_at=c.created_at,
            like_count=c.like_count,
            liked_by_me=c.id in liked,
            image_url=storage.signed_url(c.image_key) if c.image_key else None,
            look=look,
            previews=await previews(db, c.body),
        )
    return out


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
async def list_comments(post_id: str, me: CurrentUser, db: DbSession):
    """The whole conversation as a tree: comments, replies, replies to replies."""
    post = await _visible_post(db, post_id, me)
    rows = (
        await db.execute(
            select(PostComment, User)
            .join(User, User.id == PostComment.user_id)
            .where(PostComment.post_id == post.id, PostComment.is_hidden.is_(False), User.community_banned_at.is_(None))
            .order_by(PostComment.created_at)
        )
    ).all()
    by_id = await _comments_out(db, [(c, u) for c, u in rows], me, post.user_id)
    top: list[CommentOut] = []
    placed: set[str] = set()
    for c, _ in rows:  # oldest first, so a parent is always placed before its replies
        out = by_id[c.id]
        if c.parent_id is None:
            top.append(out)
        elif c.parent_id in placed:
            by_id[c.parent_id].replies.append(out)
        else:
            continue  # its parent was hidden or removed: the reply goes with it
        placed.add(c.id)
    return top


@router.post(
    "/comment-images",
    dependencies=[Depends(rate_limiter("community_comment_image", limit=40, window_seconds=3600))],
)
async def upload_comment_image(me: CurrentUser, file: UploadFile = File(...)):
    """A photo for a comment, uploaded first so the member sees it before posting."""
    from app.services import community_media

    _can_write(me)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please choose a photo.")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="That photo is too big. Please use one under 15 MB.")
    if community_media.video_kind(raw) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comments take photos. Post a video as its own post.")
    key, _, _ = await community_media.save_image(me.id, raw)
    return {"image_key": key, "image_url": get_storage().signed_url(key)}


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("community_comment", limit=60, window_seconds=3600))],
)
async def add_comment(post_id: str, payload: NewCommentIn, me: CurrentUser, db: DbSession):
    _can_write(me)
    post = await _visible_post(db, post_id, me)
    parent = None
    if payload.parent_id:
        parent = await db.get(PostComment, payload.parent_id)
        if parent is None or parent.post_id != post.id or parent.is_hidden:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    image_key = None
    if payload.image_key:
        # only a photo this member uploaded themselves
        if not re.fullmatch(rf"community/{re.escape(me.id)}/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)", payload.image_key):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please add the photo again.")
        image_key = payload.image_key
    job_id = None
    if payload.tryon_job_id:
        job = await db.scalar(select(TryOnJob).where(TryOnJob.id == payload.tryon_job_id).options(selectinload(TryOnJob.result)))
        if job is None or job.user_id != me.id or job.status != JobStatus.COMPLETED or job.result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Look not found")
        job_id = job.id
    body, removed = clean_text(payload.body)
    if not body and not image_key and not job_id:
        detail = (
            "Links to other websites can't be shared here. You can share TryOnU store and product links."
            if removed
            else "Write a comment, or add a photo or a look."
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    await ensure_handle(db, me)
    comment = PostComment(
        post_id=post.id, user_id=me.id, parent_id=parent.id if parent else None, body=body, image_key=image_key,
        tryon_job_id=job_id, links_removed=removed,
    )
    db.add(comment)
    await db.flush()
    await _recount_comments(db, post)
    await db.commit()
    await db.refresh(comment)
    out = (await _comments_out(db, [(comment, me)], me, post.user_id))[comment.id]
    if parent is not None:
        parent_author = await db.get(User, parent.user_id)
        out.reply_to = parent_author.handle if parent_author else None
    out.links_removed = removed
    return out


async def _thread_ids(db: DbSession, root_id: str) -> list[str]:
    """A comment and every reply under it, however deep."""
    ids, frontier = [root_id], [root_id]
    while frontier:
        frontier = list((await db.execute(select(PostComment.id).where(PostComment.parent_id.in_(frontier)))).scalars())
        ids.extend(frontier)
    return ids


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: str, me: CurrentUser, db: DbSession):
    comment = await db.get(PostComment, comment_id)
    post = await db.get(CommunityPost, comment.post_id) if comment else None
    if comment is None or post is None or not (comment.user_id == me.id or post.user_id == me.id or me.is_admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    ids = await _thread_ids(db, comment.id)
    images = list(
        (await db.execute(select(PostComment.image_key).where(PostComment.id.in_(ids), PostComment.image_key.is_not(None)))).scalars()
    )
    await db.execute(delete(CommentLike).where(CommentLike.comment_id.in_(ids)))
    await db.execute(delete(CommunityReport).where(CommunityReport.comment_id.in_(ids)))
    for cid in reversed(ids):  # the deepest replies first
        await db.execute(delete(PostComment).where(PostComment.id == cid))
    db.expunge(comment)
    await db.flush()
    await _recount_comments(db, post)
    await db.commit()
    from app.services.community_media import delete_files

    delete_files(*images)


async def _visible_comment(db: DbSession, comment_id: str, me: User) -> PostComment:
    comment = await db.get(PostComment, comment_id)
    if comment is None or comment.is_hidden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    await _visible_post(db, comment.post_id, me)
    return comment


async def _recount_comment_likes(db: DbSession, comment: PostComment) -> None:
    comment.like_count = int(
        await db.scalar(select(func.count()).select_from(CommentLike).where(CommentLike.comment_id == comment.id)) or 0
    )


@router.post("/comments/{comment_id}/like", dependencies=[Depends(rate_limiter("community_like", limit=400, window_seconds=3600))])
async def like_comment(comment_id: str, me: CurrentUser, db: DbSession):
    _can_write(me)
    comment = await _visible_comment(db, comment_id, me)
    if await db.scalar(select(CommentLike.id).where(CommentLike.comment_id == comment.id, CommentLike.user_id == me.id)) is None:
        db.add(CommentLike(comment_id=comment.id, user_id=me.id))
        await db.flush()
    await _recount_comment_likes(db, comment)
    await db.commit()
    return {"liked": True, "like_count": comment.like_count}


@router.delete("/comments/{comment_id}/like")
async def unlike_comment(comment_id: str, me: CurrentUser, db: DbSession):
    comment = await _visible_comment(db, comment_id, me)
    await db.execute(delete(CommentLike).where(CommentLike.comment_id == comment.id, CommentLike.user_id == me.id))
    await _recount_comment_likes(db, comment)
    await db.commit()
    return {"liked": False, "like_count": comment.like_count}


@router.post("/comments/{comment_id}/try", response_model=TryThisOut)
async def try_comment_look(comment_id: str, me: CurrentUser, db: DbSession):
    """The look someone added to a comment, ready to try on with my own photo."""
    comment = await _visible_comment(db, comment_id, me)
    job = (
        await db.scalar(select(TryOnJob).where(TryOnJob.id == comment.tryon_job_id).options(selectinload(TryOnJob.result)))
        if comment.tryon_job_id
        else None
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This comment has no look to try on.")
    outfit_id, product_id = await copy_look(db, me.id, job, include_hidden=True)
    if outfit_id is None and product_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The products in this look aren't available anymore.")
    return TryThisOut(outfit_id=outfit_id, product_id=product_id)


# ------------------------------------------------------------------ profiles and following


class ProfileOut(BaseModel):
    handle: str
    name: str | None
    avatar_url: str | None
    bio: str | None
    posts: int
    followers: int
    following: int
    followed_by_me: bool
    is_me: bool


async def _profile_out(db: DbSession, user: User, me: User) -> ProfileOut:
    posts = await db.scalar(
        select(func.count()).select_from(CommunityPost).where(CommunityPost.user_id == user.id, CommunityPost.is_hidden.is_(False))
    )
    followers = await db.scalar(select(func.count()).select_from(Follow).where(Follow.followee_id == user.id))
    following = await db.scalar(select(func.count()).select_from(Follow).where(Follow.follower_id == user.id))
    mine = await db.scalar(select(Follow.id).where(Follow.follower_id == me.id, Follow.followee_id == user.id))
    return ProfileOut(
        handle=user.handle or "member",
        name=user.full_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        posts=int(posts or 0),
        followers=int(followers or 0),
        following=int(following or 0),
        followed_by_me=mine is not None,
        is_me=user.id == me.id,
    )


async def _by_handle(db: DbSession, handle: str) -> User:
    user = await db.scalar(select(User).where(User.handle == handle.lower().lstrip("@")))
    if user is None or user.community_banned_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This member isn't in the community")
    return user


@router.get("/me", response_model=ProfileOut)
async def my_profile(me: CurrentUser, db: DbSession):
    await ensure_handle(db, me)
    out = await _profile_out(db, me, me)
    await db.commit()
    return out


class ProfileUpdateIn(BaseModel):
    handle: str | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=280)


@router.patch("/me", response_model=ProfileOut)
async def update_my_profile(payload: ProfileUpdateIn, me: CurrentUser, db: DbSession):
    data = payload.model_dump(exclude_unset=True)
    if "handle" in data and data["handle"] is not None:
        handle = data["handle"].strip().lower().lstrip("@")
        if not HANDLE_RE.match(handle) or handle in RESERVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A username is 3–30 letters, numbers, dots or underscores.",
            )
        taken = await db.scalar(select(User.id).where(User.handle == handle, User.id != me.id))
        if taken is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That username is taken. Try another one.")
        me.handle = handle
    if "bio" in data:
        me.bio = (data["bio"] or "").strip() or None
    await db.commit()
    return await _profile_out(db, me, me)


# ------------------------------------------------------------------ profile pictures

AVATAR_PREFIX = "avatars/"
AVATAR_URL = "/api/v1/community/avatar/"


def _square_avatar(raw: bytes) -> bytes:
    """Any photo (JPEG, PNG, HEIC…), turned upright, cropped to a centred square, 400×400 JPEG."""
    import io

    from PIL import Image, ImageOps, UnidentifiedImageError

    from app.services import image_service  # noqa: F401 (registers the HEIC decoder)

    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That file isn't a photo we can read. Try a JPG or PNG.") from exc
    img = ImageOps.fit(img, (400, 400), Image.LANCZOS, centering=(0.5, 0.35))  # faces sit a little above the middle
    out = io.BytesIO()
    img.save(out, "JPEG", quality=86, optimize=True)
    return out.getvalue()


def _remove_old_avatar(user: User) -> None:
    if user.avatar_url and user.avatar_url.startswith(AVATAR_URL):
        try:
            get_storage().delete(AVATAR_PREFIX + user.avatar_url.removeprefix(AVATAR_URL))
        except Exception:  # noqa: BLE001 — a leftover file is harmless
            pass


@router.post(
    "/me/avatar",
    response_model=ProfileOut,
    dependencies=[Depends(rate_limiter("community_avatar", limit=20, window_seconds=3600))],
)
async def upload_avatar(me: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="That photo is too big. Please use one under 15 MB.")
    content = _square_avatar(raw)
    name = f"{me.id}-{secrets.token_urlsafe(8)}.jpg"
    get_storage().put(AVATAR_PREFIX + name, content, "image/jpeg")
    _remove_old_avatar(me)
    me.avatar_url = AVATAR_URL + name
    await ensure_handle(db, me)
    await db.commit()
    return await _profile_out(db, me, me)


@router.delete("/me/avatar", response_model=ProfileOut)
async def remove_avatar(me: CurrentUser, db: DbSession):
    _remove_old_avatar(me)
    me.avatar_url = None
    await db.commit()
    return await _profile_out(db, me, me)


@router.get("/avatar/{name}")
async def avatar_image(name: str):
    """A member's profile picture. Each upload gets a new random name, so it can be cached for good."""
    from fastapi import Response

    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}\.jpg", name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        data = get_storage().read(AVATAR_PREFIX + name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/profiles/{handle}", response_model=ProfileOut)
async def get_profile(handle: str, me: CurrentUser, db: DbSession):
    return await _profile_out(db, await _by_handle(db, handle), me)


@router.get("/profiles/{handle}/posts", response_model=FeedOut)
async def profile_posts(handle: str, me: CurrentUser, db: DbSession, offset: int = 0, limit: int = 18):
    user = await _by_handle(db, handle)
    limit = min(max(limit, 1), 36)
    rows = (
        await db.execute(
            select(CommunityPost)
            .where(CommunityPost.user_id == user.id, CommunityPost.is_hidden.is_(False))
            .order_by(CommunityPost.created_at.desc())
            .offset(max(offset, 0))
            .limit(limit + 1)
        )
    ).scalars().all()
    return FeedOut(posts=await _posts_out(db, list(rows[:limit]), me), next_offset=offset + limit if len(rows) > limit else None)


@router.post("/profiles/{handle}/follow", response_model=ProfileOut, dependencies=[Depends(rate_limiter("community_follow", limit=200, window_seconds=3600))])
async def follow(handle: str, me: CurrentUser, db: DbSession):
    user = await _by_handle(db, handle)
    if user.id == me.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't follow yourself.")
    if await db.scalar(select(Follow.id).where(Follow.follower_id == me.id, Follow.followee_id == user.id)) is None:
        db.add(Follow(follower_id=me.id, followee_id=user.id))
        await db.commit()
    return await _profile_out(db, user, me)


@router.delete("/profiles/{handle}/follow", response_model=ProfileOut)
async def unfollow(handle: str, me: CurrentUser, db: DbSession):
    user = await _by_handle(db, handle)
    await db.execute(delete(Follow).where(Follow.follower_id == me.id, Follow.followee_id == user.id))
    await db.commit()
    return await _profile_out(db, user, me)


# ------------------------------------------------------------------ reports


class ReportIn(BaseModel):
    post_id: str | None = None
    comment_id: str | None = None
    reason: str = Field(min_length=2, max_length=300)


@router.post("/reports", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limiter("community_report", limit=30, window_seconds=3600))])
async def report(payload: ReportIn, me: CurrentUser, db: DbSession):
    if bool(payload.post_id) == bool(payload.comment_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report one post or one comment.")
    if payload.post_id and await db.get(CommunityPost, payload.post_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if payload.comment_id and await db.get(PostComment, payload.comment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    db.add(CommunityReport(reporter_id=me.id, post_id=payload.post_id, comment_id=payload.comment_id, reason=payload.reason.strip()))
    await db.commit()
    return {"detail": "Thanks. Our team will look at it."}


# ------------------------------------------------------------------ admin: moderation


class AdminReportOut(BaseModel):
    id: str
    reason: str
    reporter_email: str
    kind: str  # "post" | "comment"
    target_id: str
    author_handle: str | None
    author_email: str | None
    text: str | None
    image_url: str | None
    video_url: str | None = None
    hidden: bool
    created_at: datetime
    resolved_at: datetime | None


@admin_router.get("/reports", response_model=list[AdminReportOut])
async def admin_reports(_: AdminUser, db: DbSession, show: str = "open"):
    query = select(CommunityReport).order_by(CommunityReport.created_at.desc()).limit(200)
    if show == "open":
        query = query.where(CommunityReport.resolved_at.is_(None))
    out: list[AdminReportOut] = []
    storage = get_storage()
    for r in (await db.execute(query)).scalars():
        reporter = await db.get(User, r.reporter_id)
        if r.post_id:
            post = await db.get(CommunityPost, r.post_id)
            if post is None:
                continue
            author = await db.get(User, post.user_id)
            video = None
            if post.media_key:
                image = storage.signed_url(post.poster_key or post.media_key) if (post.media_kind == "image" or post.poster_key) else None
                video = storage.signed_url(post.media_key) if post.media_kind == "video" else None
            else:
                job = await db.scalar(select(TryOnJob).where(TryOnJob.id == post.tryon_job_id).options(selectinload(TryOnJob.result)))
                image = storage.signed_url(job.result.storage_key) if job and job.result else None
            kind, target, text, hidden = "post", post.id, post.caption, post.is_hidden
        else:
            comment = await db.get(PostComment, r.comment_id) if r.comment_id else None
            if comment is None:
                continue
            author = await db.get(User, comment.user_id)
            kind, target, text, hidden, image, video = "comment", comment.id, comment.body, comment.is_hidden, None, None
        out.append(
            AdminReportOut(
                id=r.id,
                reason=r.reason,
                reporter_email=reporter.email if reporter else "",
                kind=kind,
                target_id=target,
                author_handle=author.handle if author else None,
                author_email=author.email if author else None,
                text=text,
                image_url=image,
                video_url=video,
                hidden=hidden,
                created_at=r.created_at,
                resolved_at=r.resolved_at,
            )
        )
    return out


class ResolveIn(BaseModel):
    action: str = Field(pattern=r"^(hide|dismiss|ban)$")


@admin_router.post("/reports/{report_id}/resolve")
async def admin_resolve(report_id: str, payload: ResolveIn, _: AdminUser, db: DbSession):
    """hide: the post/comment disappears; ban: also blocks its author from the
    community (their posts and comments disappear); dismiss: nothing wrong."""
    r = await db.get(CommunityReport, report_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    now = datetime.now(timezone.utc)
    if payload.action in ("hide", "ban"):
        author_id = None
        if r.post_id and (post := await db.get(CommunityPost, r.post_id)):
            post.is_hidden = True
            author_id = post.user_id
        if r.comment_id and (comment := await db.get(PostComment, r.comment_id)):
            comment.is_hidden = True
            author_id = comment.user_id
            parent_post = await db.get(CommunityPost, comment.post_id)
            if parent_post:
                await db.flush()
                await _recount_comments(db, parent_post)
        if payload.action == "ban" and author_id and (author := await db.get(User, author_id)):
            author.community_banned_at = now
    # every open report about the same thing is settled together
    same = select(CommunityReport).where(
        CommunityReport.resolved_at.is_(None),
        (CommunityReport.post_id == r.post_id) if r.post_id else (CommunityReport.comment_id == r.comment_id),
    )
    for other in (await db.execute(same)).scalars():
        other.resolved_at = now
    r.resolved_at = now
    await db.commit()
    return {"detail": "Done"}


@admin_router.post("/users/{user_id}/unban")
async def admin_unban(user_id: str, _: AdminUser, db: DbSession):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.community_banned_at = None
    await db.commit()
    return {"detail": "Done"}


# ------------------------------------------------------------------ admin: everything members do


class AdminStatsOut(BaseModel):
    members: int
    active_7d: int
    posts: int
    posts_7d: int
    comments: int
    comments_7d: int
    likes: int
    likes_7d: int
    comment_likes: int
    follows: int
    links_removed: int
    hidden: int
    blocked: int
    open_reports: int


@admin_router.get("/stats", response_model=AdminStatsOut)
async def admin_stats(_: AdminUser, db: DbSession):
    from datetime import timedelta

    week = datetime.now(timezone.utc) - timedelta(days=7)

    async def count(model, *where) -> int:  # noqa: ANN001
        return int(await db.scalar(select(func.count()).select_from(model).where(*where)) or 0)

    active = set((await db.execute(select(CommunityPost.user_id).where(CommunityPost.created_at >= week))).scalars())
    active |= set((await db.execute(select(PostComment.user_id).where(PostComment.created_at >= week))).scalars())
    active |= set((await db.execute(select(PostLike.user_id).where(PostLike.created_at >= week))).scalars())
    links = int(await db.scalar(select(func.coalesce(func.sum(PostComment.links_removed), 0))) or 0) + int(
        await db.scalar(select(func.coalesce(func.sum(CommunityPost.links_removed), 0))) or 0
    )
    return AdminStatsOut(
        members=await count(User, User.handle.is_not(None)),
        active_7d=len(active),
        posts=await count(CommunityPost),
        posts_7d=await count(CommunityPost, CommunityPost.created_at >= week),
        comments=await count(PostComment),
        comments_7d=await count(PostComment, PostComment.created_at >= week),
        likes=await count(PostLike),
        likes_7d=await count(PostLike, PostLike.created_at >= week),
        comment_likes=await count(CommentLike),
        follows=await count(Follow),
        links_removed=links,
        hidden=await count(CommunityPost, CommunityPost.is_hidden.is_(True)) + await count(PostComment, PostComment.is_hidden.is_(True)),
        blocked=await count(User, User.community_banned_at.is_not(None)),
        open_reports=await count(CommunityReport, CommunityReport.resolved_at.is_(None)),
    )


class AdminMemberOut(BaseModel):
    user_id: str
    handle: str
    name: str | None
    email: str
    avatar_url: str | None
    posts: int
    comments: int
    likes_given: int
    likes_received: int
    followers: int
    following: int
    links_removed: int
    last_active_at: datetime | None
    blocked_at: datetime | None
    joined_at: datetime


class AdminMembersOut(BaseModel):
    total: int
    rows: list[AdminMemberOut]


def _grouped(col, label: str = "n", value=None):  # noqa: ANN001, ANN202
    """One number per member (a count, or the given sum / latest time)."""
    return select(col.label("uid"), (value if value is not None else func.count()).label(label)).group_by(col).subquery()


@admin_router.get("/members", response_model=AdminMembersOut)
async def admin_members(_: AdminUser, db: DbSession, q: str = "", sort: str = "engaged", offset: int = 0, limit: int = 25):
    """Every community member with how much they take part: most engaged first."""
    posts = _grouped(CommunityPost.user_id)
    comments = _grouped(PostComment.user_id)
    given = _grouped(PostLike.user_id)
    received = (
        select(CommunityPost.user_id.label("uid"), func.count(PostLike.id).label("n"))
        .join(PostLike, PostLike.post_id == CommunityPost.id)
        .group_by(CommunityPost.user_id)
        .subquery()
    )
    followers = _grouped(Follow.followee_id)
    following = _grouped(Follow.follower_id)
    p_links = _grouped(CommunityPost.user_id, value=func.sum(CommunityPost.links_removed))
    c_links = _grouped(PostComment.user_id, value=func.sum(PostComment.links_removed))
    p_last = _grouped(CommunityPost.user_id, "t", func.max(CommunityPost.created_at))
    c_last = _grouped(PostComment.user_id, "t", func.max(PostComment.created_at))
    l_last = _grouped(PostLike.user_id, "t", func.max(PostLike.created_at))

    def n(sq):  # noqa: ANN001, ANN202
        return func.coalesce(sq.c.n, 0)

    score = n(posts) * 3 + n(comments) * 2 + n(given) + n(received)
    query = select(
        User, n(posts), n(comments), n(given), n(received), n(followers), n(following), n(p_links) + n(c_links),
        p_last.c.t, c_last.c.t, l_last.c.t,
    )
    for sq in (posts, comments, given, received, followers, following, p_links, c_links, p_last, c_last, l_last):
        query = query.outerjoin(sq, sq.c.uid == User.id)
    query = query.where(User.handle.is_not(None))
    if q.strip():
        like = f"%{q.strip().lower().lstrip('@')}%"
        query = query.where(
            or_(func.lower(User.handle).like(like), func.lower(User.email).like(like), func.lower(User.full_name).like(like))
        )
    if sort == "blocked":
        query = query.where(User.community_banned_at.is_not(None))
    total = int(await db.scalar(select(func.count()).select_from(query.with_only_columns(User.id).subquery())) or 0)
    order = User.created_at.desc() if sort == "newest" else score.desc()
    rows = (
        await db.execute(query.order_by(order, User.created_at.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 100)))
    ).all()

    def latest(*times):  # noqa: ANN001, ANN202
        found = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in times if t is not None]
        return max(found) if found else None

    return AdminMembersOut(
        total=total,
        rows=[
            AdminMemberOut(
                user_id=u.id, handle=u.handle or "member", name=u.full_name, email=u.email, avatar_url=u.avatar_url,
                posts=np, comments=nc, likes_given=ng, likes_received=nr, followers=nf, following=nfg, links_removed=nl,
                last_active_at=latest(t1, t2, t3), blocked_at=u.community_banned_at, joined_at=u.created_at,
            )
            for u, np, nc, ng, nr, nf, nfg, nl, t1, t2, t3 in rows
        ],
    )


class AdminCommentOut(BaseModel):
    id: str
    post_id: str
    post_caption: str | None
    post_author_handle: str | None
    author: AuthorOut
    author_email: str
    author_id: str
    body: str
    reply_to: str | None
    image_url: str | None
    look_image_url: str | None
    like_count: int
    links_removed: int
    hidden: bool
    created_at: datetime


class AdminCommentsOut(BaseModel):
    total: int
    rows: list[AdminCommentOut]


async def _jobs_with_results(db: DbSession, job_ids: list[str]) -> dict[str, TryOnJob]:
    if not job_ids:
        return {}
    rows = await db.execute(select(TryOnJob).where(TryOnJob.id.in_(job_ids)).options(selectinload(TryOnJob.result)))
    return {j.id: j for j in rows.scalars()}


@admin_router.get("/comments", response_model=AdminCommentsOut)
async def admin_comments(
    _: AdminUser, db: DbSession, q: str = "", member: str = "", show: str = "all", offset: int = 0, limit: int = 25
):
    """Every comment and reply, newest first; by one member, or with a word in it."""
    query = select(PostComment, User).join(User, User.id == PostComment.user_id)
    if member.strip():
        query = query.where(User.handle == member.strip().lower().lstrip("@"))
    if q.strip():
        query = query.where(func.lower(PostComment.body).like(f"%{q.strip().lower()}%"))
    if show == "hidden":
        query = query.where(PostComment.is_hidden.is_(True))
    elif show == "links":
        query = query.where(PostComment.links_removed > 0)
    total = int(await db.scalar(select(func.count()).select_from(query.with_only_columns(PostComment.id).subquery())) or 0)
    rows = (
        await db.execute(query.order_by(PostComment.created_at.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 100)))
    ).all()
    post_ids = {c.post_id for c, _ in rows}
    posts = {p.id: p for p in (await db.execute(select(CommunityPost).where(CommunityPost.id.in_(post_ids)))).scalars()}
    parent_ids = {c.parent_id for c, _ in rows if c.parent_id}
    parents = dict((await db.execute(select(PostComment.id, PostComment.user_id).where(PostComment.id.in_(parent_ids)))).all())
    user_ids = {p.user_id for p in posts.values()} | set(parents.values())
    handles = dict((await db.execute(select(User.id, User.handle).where(User.id.in_(user_ids)))).all())
    jobs = await _jobs_with_results(db, [c.tryon_job_id for c, _ in rows if c.tryon_job_id])
    storage = get_storage()
    out = []
    for c, u in rows:
        post = posts.get(c.post_id)
        job = jobs.get(c.tryon_job_id) if c.tryon_job_id else None
        out.append(
            AdminCommentOut(
                id=c.id,
                post_id=c.post_id,
                post_caption=post.caption if post else None,
                post_author_handle=handles.get(post.user_id) if post else None,
                author=_author(u),
                author_email=u.email,
                author_id=u.id,
                body=c.body,
                reply_to=handles.get(parents.get(c.parent_id)) if c.parent_id else None,
                image_url=storage.signed_url(c.image_key) if c.image_key else None,
                look_image_url=storage.signed_url(job.result.storage_key) if job and job.result else None,
                like_count=c.like_count,
                links_removed=c.links_removed,
                hidden=c.is_hidden,
                created_at=c.created_at,
            )
        )
    return AdminCommentsOut(total=total, rows=out)


class AdminPostOut(BaseModel):
    id: str
    author: AuthorOut
    author_email: str
    author_id: str
    media_kind: str
    image_url: str | None
    video_url: str | None
    caption: str | None
    like_count: int
    comment_count: int
    links_removed: int
    hidden: bool
    created_at: datetime


class AdminPostsOut(BaseModel):
    total: int
    rows: list[AdminPostOut]


@admin_router.get("/posts", response_model=AdminPostsOut)
async def admin_posts(_: AdminUser, db: DbSession, member: str = "", sort: str = "newest", offset: int = 0, limit: int = 24):
    """Every post (hidden ones too), newest or most engaged first."""
    query = select(CommunityPost, User).join(User, User.id == CommunityPost.user_id)
    if member.strip():
        query = query.where(User.handle == member.strip().lower().lstrip("@"))
    if sort == "hidden":
        query = query.where(CommunityPost.is_hidden.is_(True))
    total = int(await db.scalar(select(func.count()).select_from(query.with_only_columns(CommunityPost.id).subquery())) or 0)
    order = (
        (CommunityPost.like_count + 2 * CommunityPost.comment_count).desc() if sort == "engaged" else CommunityPost.created_at.desc()
    )
    rows = (
        await db.execute(
            query.order_by(order, CommunityPost.created_at.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 96))
        )
    ).all()
    jobs = await _jobs_with_results(db, [p.tryon_job_id for p, _ in rows if p.tryon_job_id and not p.media_key])
    storage = get_storage()
    out = []
    for p, u in rows:
        if p.media_key:
            image = storage.signed_url(p.poster_key or p.media_key) if (p.poster_key or p.media_kind == "image") else None
            video = storage.signed_url(p.media_key) if p.media_kind == "video" else None
        else:
            job = jobs.get(p.tryon_job_id)
            image, video = (storage.signed_url(job.result.storage_key) if job and job.result else None), None
        out.append(
            AdminPostOut(
                id=p.id, author=_author(u), author_email=u.email, author_id=u.id, media_kind=p.media_kind, image_url=image,
                video_url=video, caption=p.caption, like_count=p.like_count, comment_count=p.comment_count,
                links_removed=p.links_removed, hidden=p.is_hidden, created_at=p.created_at,
            )
        )
    return AdminPostsOut(total=total, rows=out)


class HiddenIn(BaseModel):
    hidden: bool


@admin_router.post("/comments/{comment_id}/hidden")
async def admin_hide_comment(comment_id: str, payload: HiddenIn, _: AdminUser, db: DbSession):
    comment = await db.get(PostComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    comment.is_hidden = payload.hidden
    await db.flush()
    if post := await db.get(CommunityPost, comment.post_id):
        await _recount_comments(db, post)
    await db.commit()
    return {"hidden": comment.is_hidden}


@admin_router.post("/posts/{post_id}/hidden")
async def admin_hide_post(post_id: str, payload: HiddenIn, _: AdminUser, db: DbSession):
    post = await db.get(CommunityPost, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    post.is_hidden = payload.hidden
    await db.commit()
    return {"hidden": post.is_hidden}


@admin_router.post("/users/{user_id}/ban")
async def admin_ban(user_id: str, _: AdminUser, db: DbSession):
    """Block a member from the community: they can't post or comment, and their posts and comments disappear."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An admin can't be blocked.")
    user.community_banned_at = datetime.now(timezone.utc)
    await db.commit()
    return {"detail": "Done"}
