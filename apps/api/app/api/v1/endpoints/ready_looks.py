"""Ready looks (tryonu.app/looks): complete outfits the TryOnU team tried on a
model, with every product's shop link, for shoppers to try on themselves.

Team members make a try-on with their own credits, then publish it here; the
look gets an "outfit receipt" picture (the model and each product with its
price) for the page and for social media posts.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, OptionalUser, TeamUser
from app.core.logging import logger
from app.core.rate_limit import rate_limiter
from app.models.community import CommunityPost
from app.models.enums import Gender, JobStatus, OutfitSlot
from app.models.product import Product
from app.models.ready_look import ReadyLook, ReadyLookItem
from app.models.tryon import TryOnJob
from app.models.user import User
from app.services.storage_service import get_storage

router = APIRouter(tags=["ready looks"])

AUDIENCES = ("women", "men", "kids")
# who a look is for, from words: kids first ("Boys' winter look"), and "men"
# as a whole word so "women" never counts as men
_FOR = (
    ("kids", re.compile(r"\b(kids?|child|children|boys?|girls?|baby|babies|toddlers?|infants?|junior|youth)\b", re.I)),
    ("men", re.compile(r"\b(men|mens|men's|man|male|gents?|for him)\b", re.I)),
    ("women", re.compile(r"\b(women|womens|women's|woman|ladies|lady|female|bridal|bride|for her)\b", re.I)),
)


def _named(text: str) -> str | None:
    return next((who for who, pattern in _FOR if pattern.search(text or "")), None)


def guess_audience(title: str, products: list[Product]) -> tuple[str, bool]:
    """Who a look is for, and whether its title says so outright. The title
    decides when it names one ("Men's Winter Outfit"); otherwise most of its
    products do (their shop's gender, else their names); women if nothing tells."""
    said = _named(title)
    if said:
        return said, True
    votes = Counter()
    for product in products:
        gender = getattr(product, "gender", None)
        who = gender.value if gender in (Gender.MEN, Gender.WOMEN, Gender.KIDS) else _named(product.name)
        if who:
            votes[who] += 1
    return (votes.most_common(1)[0][0] if votes else "women"), False
_LOAD = selectinload(ReadyLook.items).selectinload(ReadyLookItem.product).selectinload(Product.images)
_LOAD_RETAILER = selectinload(ReadyLook.items).selectinload(ReadyLookItem.product).selectinload(Product.retailer)


class ReadyLookItemOut(BaseModel):
    id: str
    product_id: str
    name: str
    shop: str | None
    price_cents: int
    currency: str
    image_url: str | None
    buy_url: str


class CommunityRefOut(BaseModel):
    post_id: str
    handle: str


class ReadyLookOut(BaseModel):
    id: str
    title: str
    audience: str
    season: str | None
    card_url: str
    card_small_url: str
    image_url: str
    is_published: bool
    sort_order: int
    items: list[ReadyLookItemOut]
    total_cents: int | None
    currency: str | None
    created_by: str | None = None
    created_at: datetime | None = None
    # the outfit picture's layout (1080 x 1350): the try-on picture and each
    # product card ("item" = its place in items), for drawing the cards as links
    layout: dict | None = None
    # team panel only: made by the signed-in team member, and the try-on it came from
    mine: bool = False
    tryon_job_id: str | None = None
    community: list[CommunityRefOut] = []  # its posts on the community feed (team panel)


class PublishIn(BaseModel):
    tryon_job_id: str
    title: str = Field(min_length=2, max_length=120)
    # None: worked out from the title and the products
    audience: str | None = Field(default=None, pattern="^(women|men|kids)$")
    season: str | None = Field(default="Winter", max_length=24)
    # False: saved as a draft (hidden), published later from the team panel
    publish: bool = True


class LookUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    audience: str | None = Field(default=None, pattern="^(women|men|kids)$")
    season: str | None = Field(default=None, max_length=24)
    is_published: bool | None = None
    sort_order: int | None = Field(default=None, ge=-1000, le=1000)


def _api() -> str:
    return get_settings().PUBLIC_API_BASE_URL.rstrip("/")


def _out(look: ReadyLook, creator: str | None = None, me: User | None = None) -> ReadyLookOut:
    base = f"{_api()}/api/v1/looks/{look.id}"
    items = []
    for it in look.items:
        p = it.product
        items.append(
            ReadyLookItemOut(
                id=it.id,
                product_id=p.id,
                name=p.name,
                shop=p.merchant_name or (p.retailer.name if p.retailer else None),
                price_cents=p.price_cents,
                currency=p.currency,
                image_url=p.primary_image_url,
                buy_url=f"{_api()}/api/v1/affiliate/go/{p.id}?source=ready_look",
            )
        )
    currencies = {i.currency.lower() for i in items}
    same = len(currencies) == 1
    return ReadyLookOut(
        id=look.id,
        title=look.title,
        audience=look.audience,
        season=look.season,
        card_url=f"{base}/card.jpg?v={look.version}",
        card_small_url=f"{base}/card.jpg?v={look.version}&size=small",
        image_url=f"{base}/image.jpg?v={look.version}",
        is_published=look.is_published,
        sort_order=look.sort_order,
        items=items,
        total_cents=sum(i.price_cents for i in items) if same and items else None,
        currency=items[0].currency if same and items else None,
        created_by=creator,
        created_at=look.created_at,
        layout=json.loads(look.layout) if look.layout else None,
        mine=bool(me and look.created_by == me.id),
        tryon_job_id=look.tryon_job_id if me else None,
    )


async def _get(db: DbSession, look_id: str) -> ReadyLook:
    look = await db.scalar(select(ReadyLook).where(ReadyLook.id == look_id).options(_LOAD, _LOAD_RETAILER))
    if look is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This look isn't available")
    return look


async def _render(db: DbSession, look: ReadyLook) -> None:
    """(Re)make the outfit-receipt pictures (full and a small one for the page's
    grid) from the model picture and the products as they are now."""
    from PIL import Image

    from app.services.price_alert_service import price_text
    from app.services.ready_look_card import CardItem, render_card
    from app.services.tryon_direct.inputs import fetch_product_image

    async def photo(url: str | None) -> bytes | None:
        if not url:
            return None
        try:
            return await fetch_product_image(url)
        except Exception:  # noqa: BLE001 - a missing photo leaves its box empty
            return None

    storage = get_storage()
    person = await asyncio.to_thread(storage.read, look.image_key)
    photos = await asyncio.gather(*(photo(it.product.primary_image_url) for it in look.items))
    cards = [
        CardItem(
            name=it.product.name,
            price=price_text(it.product.price_cents, it.product.currency),
            image=pic,
            box=tuple(json.loads(it.box)) if it.box else None,  # type: ignore[arg-type]
        )
        for it, pic in zip(look.items, photos)
    ]
    data, layout = await asyncio.to_thread(render_card, look.title, person, cards)
    look.layout = json.dumps(layout)

    def small(jpeg: bytes) -> bytes:
        import io

        img = Image.open(io.BytesIO(jpeg))
        img.thumbnail((540, 675))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=84, optimize=True, progressive=True)
        return out.getvalue()

    old = look.card_key
    look.version += 1 if look.card_key else 0
    key = f"ready-looks/{look.id}/card-v{look.version}.jpg"
    await asyncio.to_thread(storage.put, key, data, "image/jpeg")
    await asyncio.to_thread(storage.put, key.replace(".jpg", "-sm.jpg"), await asyncio.to_thread(small, data), "image/jpeg")
    look.card_key = key
    if old and old != key:
        for k in (old, old.replace(".jpg", "-sm.jpg")):
            try:
                await asyncio.to_thread(storage.delete, k)
            except Exception:  # noqa: BLE001 - a leftover old picture is harmless
                pass


# ------------------------------------------------------------------ the public page


@router.get("/looks", response_model=list[ReadyLookOut], dependencies=[Depends(rate_limiter("looks_list", limit=600, window_seconds=3600))])
async def list_looks(db: DbSession, audience: str | None = None, limit: int = Query(default=48, ge=1, le=96)):
    """Published looks, the team's chosen order first, newest next."""
    stmt = select(ReadyLook).where(ReadyLook.is_published.is_(True)).options(_LOAD, _LOAD_RETAILER)
    if audience in AUDIENCES:
        stmt = stmt.where(ReadyLook.audience == audience)
    looks = (await db.execute(stmt.order_by(ReadyLook.sort_order.desc(), ReadyLook.created_at.desc()).limit(limit))).scalars().all()
    return [_out(look) for look in looks if look.card_key]


@router.get("/looks/{look_id}", response_model=ReadyLookOut, dependencies=[Depends(rate_limiter("looks_one", limit=1200, window_seconds=3600))])
async def get_look(look_id: str, db: DbSession, user: OptionalUser):
    look = await _get(db, look_id)
    if not look.is_published and not (user and (user.is_team or user.is_admin)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This look isn't available")
    return _out(look)


def _image_response(data: bytes) -> Response:
    # the URL carries ?v=<version>, so a new picture always gets a new address
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800, immutable"})


@router.get("/looks/{look_id}/card.jpg", dependencies=[Depends(rate_limiter("looks_image", limit=3000, window_seconds=3600))])
async def look_card(look_id: str, db: DbSession, size: str | None = None):
    look = await db.get(ReadyLook, look_id)
    if look is None or not look.card_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    key = look.card_key.replace(".jpg", "-sm.jpg") if size == "small" else look.card_key
    return _image_response(await asyncio.to_thread(get_storage().read, key))


@router.get("/looks/{look_id}/image.jpg", dependencies=[Depends(rate_limiter("looks_image", limit=3000, window_seconds=3600))])
async def look_image(look_id: str, db: DbSession):
    look = await db.get(ReadyLook, look_id)
    if look is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _image_response(await asyncio.to_thread(get_storage().read, look.image_key))


class TryLookOut(BaseModel):
    outfit_id: str | None
    product_id: str | None


@router.post("/looks/{look_id}/try", response_model=TryLookOut, dependencies=[Depends(rate_limiter("looks_try", limit=60, window_seconds=3600))])
async def try_look(look_id: str, user: CurrentUser, db: DbSession):
    """A shopper tries a Ready look on themselves: its products become their
    own outfit, ready on the try-on page with their own photo."""
    from app.models.outfit import Outfit, OutfitItem
    from app.services.outfit_slots import slot_for

    look = await _get(db, look_id)
    # every product, even one no longer in search: an outfit doesn't need search
    products = [it.product for it in look.items]
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The products in this look aren't available anymore.")
    if len(products) == 1:
        return TryLookOut(outfit_id=None, product_id=products[0].id)
    outfit = Outfit(user_id=user.id, name=look.title[:120])
    db.add(outfit)
    await db.flush()
    for pos, p in enumerate(products[:10]):
        db.add(OutfitItem(outfit_id=outfit.id, product_id=p.id, slot=slot_for(p.name) or OutfitSlot.OTHER, position=pos))
    await db.commit()
    return TryLookOut(outfit_id=outfit.id, product_id=None)


# ------------------------------------------------------------------ the team panel


@router.get("/team/looks", response_model=list[ReadyLookOut])
async def team_looks(me: TeamUser, db: DbSession):
    """Every Ready look, hidden ones included, with who made it."""
    looks = (
        await db.execute(
            select(ReadyLook).options(_LOAD, _LOAD_RETAILER).order_by(ReadyLook.sort_order.desc(), ReadyLook.created_at.desc())
        )
    ).scalars().all()
    emails = dict(
        (await db.execute(select(User.id, User.email).where(User.id.in_([lk.created_by for lk in looks if lk.created_by] or [""])))).all()
    )
    job_ids = [lk.tryon_job_id for lk in looks if lk.tryon_job_id]
    posted: dict[str, list[CommunityRefOut]] = {}
    for job_id, post_id, handle in (
        await db.execute(
            select(CommunityPost.tryon_job_id, CommunityPost.id, User.handle)
            .join(User, User.id == CommunityPost.user_id)
            .where(CommunityPost.tryon_job_id.in_(job_ids or [""]), CommunityPost.is_hidden.is_(False))
        )
    ).all():
        posted.setdefault(job_id, []).append(CommunityRefOut(post_id=post_id, handle=handle or "member"))
    out = []
    for look in looks:
        item = _out(look, emails.get(look.created_by or ""), me)
        item.community = posted.get(look.tryon_job_id or "", [])
        out.append(item)
    return out


@router.post("/team/looks", response_model=ReadyLookOut, status_code=status.HTTP_201_CREATED)
async def publish_look(payload: PublishIn, me: TeamUser, db: DbSession):
    """A finished try-on of the team member's becomes a Ready look: its picture
    is copied, its products listed, and the outfit-receipt picture made."""
    from app.services.look_products import look_products
    from app.services.storage_service import new_key

    job = await db.scalar(select(TryOnJob).where(TryOnJob.id == payload.tryon_job_id).options(selectinload(TryOnJob.result)))
    if job is None or (job.user_id != me.id and not me.is_admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Try-on not found")
    if job.status != JobStatus.COMPLETED or job.result is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That try-on isn't finished yet.")
    pairs, _ = await look_products(db, job)
    if not pairs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That try-on has no shop products to list.")
    boxes = {
        pl.get("product_id"): pl.get("box")
        for pl in (job.result.placements or [])
        if isinstance(pl, dict) and pl.get("drawn") and pl.get("box")
    }

    storage = get_storage()
    audience = payload.audience or guess_audience(payload.title, [product for product, _slot in pairs])[0]
    look = ReadyLook(
        title=payload.title.strip(), audience=audience, season=(payload.season or "").strip() or None,
        created_by=me.id, tryon_job_id=job.id, image_key="pending", is_published=payload.publish,
    )
    db.add(look)
    await db.flush()
    src = job.result.storage_key
    ext = "png" if src.lower().endswith(".png") else "jpg"
    key = new_key("ready-looks", look.id, f"model.{ext}")
    await asyncio.to_thread(storage.put, key, await asyncio.to_thread(storage.read, src), f"image/{'png' if ext == 'png' else 'jpeg'}")
    look.image_key = key
    for pos, (product, _slot) in enumerate(pairs[:10]):
        box = boxes.get(product.id)
        db.add(ReadyLookItem(look_id=look.id, product_id=product.id, position=pos, box=json.dumps(box) if box else None))
    await db.commit()
    look = await _get(db, look.id)
    await _render(db, look)
    await db.commit()
    logger.info("ready_look_published", look_id=look.id, by=me.id, items=len(look.items))
    return _out(await _get(db, look.id), me.email, me)


@router.patch("/team/looks/{look_id}", response_model=ReadyLookOut)
async def update_look(look_id: str, payload: LookUpdateIn, me: TeamUser, db: DbSession):
    look = await _get(db, look_id)
    changes = payload.model_dump(exclude_unset=True)
    retitled = "title" in changes and changes["title"] and changes["title"].strip() != look.title
    for field, value in changes.items():
        if value is not None or field == "season":
            setattr(look, field, value.strip() if isinstance(value, str) else value)
    if retitled:
        await _render(db, look)
    await db.commit()
    return _out(await _get(db, look_id), me=me)


@router.post("/team/looks/{look_id}/refresh", response_model=ReadyLookOut)
async def refresh_look(look_id: str, me: TeamUser, db: DbSession):
    """Make the outfit-receipt picture again (prices and product photos as they are now)."""
    look = await _get(db, look_id)
    await _render(db, look)
    await db.commit()
    return _out(await _get(db, look_id), me=me)


@router.delete("/team/looks/{look_id}/items/{item_id}", response_model=ReadyLookOut)
async def remove_item(look_id: str, item_id: str, me: TeamUser, db: DbSession):
    look = await _get(db, look_id)
    item = next((it for it in look.items if it.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in this look")
    if len(look.items) == 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A look needs at least one product. Delete the look instead.")
    look.items.remove(item)
    await db.flush()
    await _render(db, look)
    await db.commit()
    return _out(await _get(db, look_id), me=me)


@router.delete("/team/looks/{look_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_look(look_id: str, _: TeamUser, db: DbSession):
    look = await db.get(ReadyLook, look_id)
    if look is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    keys = [look.image_key] + ([look.card_key, look.card_key.replace(".jpg", "-sm.jpg")] if look.card_key else [])
    await db.delete(look)
    await db.commit()
    for k in keys:
        try:
            await asyncio.to_thread(get_storage().delete, k)
        except Exception:  # noqa: BLE001 - a leftover file is harmless
            pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)
