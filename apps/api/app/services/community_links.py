"""Links in community captions and comments.

Members may share TryOnU's own links: a store, a product, a shared look, a
community post. Every other link (and email address) is taken out before the
text is saved, so promotion and spam never show; the member is told how many
were removed. TryOnU links get a small preview card."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings

# common endings, so "Size M.Thanks" isn't mistaken for a web address
_TLDS = (
    "com|net|org|info|biz|io|co|app|dev|ai|me|tv|ly|gl|gg|link|page|site|online|store|shop|xyz|top|club|live|"
    "pk|in|uk|us|ae|sa|qa|bd|lk|my|sg|au|ca|de|fr|it|es|nl|be|ch|se|no|dk|pl|tr|ru|cn|jp|kr|br|mx|za|ng|eg|"
    "id|ph|vn|th|nz|ie|pt|gr|at|cz|ro|hu|ua|il|ir|iq|kw|om|bh|jo|lb|ke|gh|ma|tn|fm|to|ws|cc|su|eu|asia|"
    "tk|ml|ga|cf|me|ink|fun|space|website|tech|blog|news|today|world|life|love|fashion|clothing|boutique|style"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)
_URL = re.compile(
    rf"""(?<![@\w.])(?:(?:https?://|www\.)[^\s<>"']+|(?:[a-z0-9-]+\.)+(?:{_TLDS})(?::\d+)?(?:/[^\s<>"']*)?)(?![\w-])""",
    re.IGNORECASE,
)
_TRAILING = ".,!?;:)]}'\""
OWN_HOSTS = {"tryonu.app", "www.tryonu.app", "api.tryonu.app"}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _web_hosts() -> set[str]:
    s = get_settings()
    return {"tryonu.app", "www.tryonu.app", _host(str(s.FRONTEND_URL))} - {""}


def _api_hosts() -> set[str]:
    return {"api.tryonu.app", _host(get_settings().PUBLIC_API_BASE_URL)} - {""}


def _absolute(url: str) -> str:
    return url if re.match(r"(?i)^https?://", url) else f"https://{url}"


def is_allowed(url: str) -> bool:
    """A TryOnU page, or a TryOnU product's shop link."""
    full = _absolute(url)
    host = _host(full)
    if host in _web_hosts():
        return True
    return host in _api_hosts() and urlparse(full).path.startswith("/api/v1/affiliate/go/")


def _split_trailing(url: str) -> tuple[str, str]:
    trail = ""
    while url and url[-1] in _TRAILING:
        trail = url[-1] + trail
        url = url[:-1]
    return url, trail


def clean_text(text: str | None) -> tuple[str, int]:
    """The text without outside links and email addresses, and how many were removed."""
    if not text:
        return "", 0
    removed = 0

    def drop_email(_: re.Match) -> str:
        nonlocal removed
        removed += 1
        return ""

    def check_url(m: re.Match) -> str:
        nonlocal removed
        url, trail = _split_trailing(m.group(0))
        if url and is_allowed(url):
            return url + trail
        removed += 1
        return trail

    out = _URL.sub(check_url, _EMAIL.sub(drop_email, text))
    if removed:
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = "\n".join(line.strip() for line in out.splitlines())
    return out.strip(), removed


def own_links(text: str | None) -> list[str]:
    """The TryOnU links in a (cleaned) text, each once, in order."""
    found: list[str] = []
    for m in _URL.finditer(text or ""):
        url, _ = _split_trailing(m.group(0))
        if url and is_allowed(url) and url not in found:
            found.append(url)
    return found


class LinkPreviewOut(BaseModel):
    url: str  # where the card goes (a TryOnU path for our own pages)
    kind: str  # store | product | look | post
    title: str
    subtitle: str | None = None
    image_url: str | None = None
    price_cents: int | None = None
    currency: str | None = None


async def previews(db: AsyncSession, text: str | None, limit: int = 3) -> list[LinkPreviewOut]:
    """Cards for the TryOnU store, product, look and post links in a text."""
    out: list[LinkPreviewOut] = []
    for raw in own_links(text):
        if len(out) >= limit:
            break
        try:
            card = await _preview(db, _absolute(raw))
        except Exception:  # noqa: BLE001 — a link without a card is still a link
            card = None
        if card is not None:
            out.append(card)
    return out


async def _preview(db: AsyncSession, url: str) -> LinkPreviewOut | None:
    from app.models.community import CommunityPost
    from app.models.product import Product
    from app.models.shared_look import SharedLook
    from app.models.store import Store
    from app.models.tryon import TryOnJob
    from app.services import store_service
    from app.services.storage_service import get_storage

    parts = urlparse(url)
    path = parts.path.rstrip("/")
    segs = [s for s in path.split("/") if s]

    product_id = None
    if path.startswith("/api/v1/affiliate/go/") and len(segs) >= 5:
        product_id = segs[4]
    elif path == "/try":
        product_id = (parse_qs(parts.query).get("product") or [None])[0]
    if product_id:
        p = await db.scalar(select(Product).where(Product.id == product_id).options(selectinload(Product.images), selectinload(Product.retailer)))
        if p is None:
            return None
        return LinkPreviewOut(
            url=f"/try?product={p.id}",
            kind="product",
            title=p.name,
            subtitle=p.merchant_name or (p.retailer.name if p.retailer else None),
            image_url=p.primary_image_url,
            price_cents=p.price_cents,
            currency=p.currency,
        )

    if len(segs) == 2 and segs[0] == "stores":
        store = await db.scalar(select(Store).where(Store.slug == segs[1], Store.status == "approved"))
        if store is None or not store_service.is_live(store):
            return None
        return LinkPreviewOut(
            url=f"/stores/{store.slug}",
            kind="store",
            title=store.name,
            subtitle=(store.description or "A store on TryOnU")[:120],
            image_url=store_service.image_url(store.logo_key) if store.logo_key else None,
        )

    if len(segs) == 2 and segs[0] == "look":
        look = await db.scalar(select(SharedLook).where(SharedLook.token == segs[1], SharedLook.revoked_at.is_(None)))
        if look is None:
            return None
        api = get_settings().PUBLIC_API_BASE_URL.rstrip("/")
        return LinkPreviewOut(
            url=f"/look/{look.token}", kind="look", title="A look on TryOnU", subtitle="Try it on yourself",
            image_url=f"{api}/api/v1/shared/{look.token}/image",
        )

    if len(segs) == 3 and segs[:2] == ["community", "post"]:
        post = await db.get(CommunityPost, segs[2])
        if post is None or post.is_hidden:
            return None
        storage = get_storage()
        image = None
        if post.media_key:
            image = storage.signed_url(post.poster_key or post.media_key) if (post.poster_key or post.media_kind == "image") else None
        elif post.tryon_job_id:
            job = await db.scalar(select(TryOnJob).where(TryOnJob.id == post.tryon_job_id).options(selectinload(TryOnJob.result)))
            image = storage.signed_url(job.result.storage_key) if job and job.result else None
        return LinkPreviewOut(
            url=f"/community/post/{post.id}", kind="post", title=(post.caption or "A post in the community")[:100],
            subtitle="TryOnU community", image_url=image,
        )
    return None
