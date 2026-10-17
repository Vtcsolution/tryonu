"""The TryOnU community (signed-in members only).

Members post finished looks with a caption; others like them, comment (with
one level of replies), follow the people whose style they like, and press
"Try this look" to put the same products on their own photo. Anyone can
report a post or comment; admins hide content or block a member from the
community (Admin -> Community)."""

from __future__ import annotations

import math
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.models.community import CommunityPost, CommunityReport, Follow, PostComment, PostLike
from app.models.enums import JobStatus
from app.models.tryon import TryOnJob
from app.models.user import User
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
    image_url: str | None
    caption: str | None
    like_count: int
    comment_count: int
    liked_by_me: bool
    following_author: bool
    is_mine: bool
    products: list[LookProductOut]
    created_at: datetime


async def _posts_out(db: DbSession, posts: list[CommunityPost], me: User) -> list[PostOut]:
    if not posts:
        return []
    ids = [p.id for p in posts]
    authors = {u.id: u for u in (await db.execute(select(User).where(User.id.in_({p.user_id for p in posts})))).scalars()}
    liked = set((await db.execute(select(PostLike.post_id).where(PostLike.user_id == me.id, PostLike.post_id.in_(ids)))).scalars())
    following = set(
        (await db.execute(select(Follow.followee_id).where(Follow.follower_id == me.id, Follow.followee_id.in_(authors.keys())))).scalars()
    )
    jobs = {
        j.id: j
        for j in (
            await db.execute(select(TryOnJob).where(TryOnJob.id.in_([p.tryon_job_id for p in posts])).options(selectinload(TryOnJob.result)))
        ).scalars()
    }
    storage = get_storage()
    api = get_settings().PUBLIC_API_BASE_URL.rstrip("/")
    out: list[PostOut] = []
    for p in posts:
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
    post = CommunityPost(user_id=me.id, tryon_job_id=job.id, caption=(payload.caption or "").strip() or None)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return (await _posts_out(db, [post], me))[0]


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
    await db.delete(post)
    await db.commit()


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


class TryThisOut(BaseModel):
    outfit_id: str | None = None
    product_id: str | None = None


@router.post("/posts/{post_id}/try", response_model=TryThisOut)
async def try_post_look(post_id: str, me: CurrentUser, db: DbSession):
    """The same products, ready to try on with my own photo."""
    post = await _visible_post(db, post_id, me)
    job = await db.scalar(select(TryOnJob).where(TryOnJob.id == post.tryon_job_id).options(selectinload(TryOnJob.result)))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    outfit_id, product_id = await copy_look(db, me.id, job, include_hidden=True)
    if outfit_id is None and product_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The products in this look aren't available anymore.")
    return TryThisOut(outfit_id=outfit_id, product_id=product_id)


# ------------------------------------------------------------------ comments


class CommentOut(BaseModel):
    id: str
    author: AuthorOut
    body: str
    parent_id: str | None
    is_mine: bool
    can_delete: bool
    created_at: datetime
    replies: list["CommentOut"] = []


class NewCommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    parent_id: str | None = None


async def _recount_comments(db: DbSession, post: CommunityPost) -> None:
    post.comment_count = int(
        await db.scalar(
            select(func.count()).select_from(PostComment).where(PostComment.post_id == post.id, PostComment.is_hidden.is_(False))
        )
        or 0
    )


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
async def list_comments(post_id: str, me: CurrentUser, db: DbSession):
    post = await _visible_post(db, post_id, me)
    rows = (
        await db.execute(
            select(PostComment, User)
            .join(User, User.id == PostComment.user_id)
            .where(PostComment.post_id == post.id, PostComment.is_hidden.is_(False), User.community_banned_at.is_(None))
            .order_by(PostComment.created_at)
        )
    ).all()
    by_id: dict[str, CommentOut] = {}
    top: list[CommentOut] = []
    for c, u in rows:
        out = CommentOut(
            id=c.id,
            author=_author(u),
            body=c.body,
            parent_id=c.parent_id,
            is_mine=c.user_id == me.id,
            can_delete=c.user_id == me.id or post.user_id == me.id or me.is_admin,
            created_at=c.created_at,
        )
        by_id[c.id] = out
        parent = by_id.get(c.parent_id) if c.parent_id else None
        (parent.replies if parent else top).append(out)
    return top


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("community_comment", limit=60, window_seconds=3600))],
)
async def add_comment(post_id: str, payload: NewCommentIn, me: CurrentUser, db: DbSession):
    _can_write(me)
    post = await _visible_post(db, post_id, me)
    parent_id = None
    if payload.parent_id:
        parent = await db.get(PostComment, payload.parent_id)
        if parent is None or parent.post_id != post.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        parent_id = parent.parent_id or parent.id  # replies stay one level deep
    await ensure_handle(db, me)
    comment = PostComment(post_id=post.id, user_id=me.id, parent_id=parent_id, body=payload.body.strip())
    db.add(comment)
    await db.flush()
    await _recount_comments(db, post)
    await db.commit()
    await db.refresh(comment)
    return CommentOut(
        id=comment.id, author=_author(me), body=comment.body, parent_id=comment.parent_id, is_mine=True, can_delete=True,
        created_at=comment.created_at,
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: str, me: CurrentUser, db: DbSession):
    comment = await db.get(PostComment, comment_id)
    post = await db.get(CommunityPost, comment.post_id) if comment else None
    if comment is None or post is None or not (comment.user_id == me.id or post.user_id == me.id or me.is_admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    await db.execute(delete(PostComment).where(PostComment.parent_id == comment.id))
    await db.delete(comment)
    await db.flush()
    await _recount_comments(db, post)
    await db.commit()


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
            job = await db.scalar(select(TryOnJob).where(TryOnJob.id == post.tryon_job_id).options(selectinload(TryOnJob.result)))
            image = storage.signed_url(job.result.storage_key) if job and job.result else None
            kind, target, text, hidden = "post", post.id, post.caption, post.is_hidden
        else:
            comment = await db.get(PostComment, r.comment_id) if r.comment_id else None
            if comment is None:
                continue
            author = await db.get(User, comment.user_id)
            kind, target, text, hidden, image = "comment", comment.id, comment.body, comment.is_hidden, None
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
