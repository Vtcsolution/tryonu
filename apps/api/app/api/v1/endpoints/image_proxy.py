"""Product photos through TryOnU's own server.

Shoppers' internet providers sometimes can't reach a retailer's image server
(eBay's and AliExpress's photos sit on CDNs whose routes from some networks
time out), which left white boxes where products should be. The website asks
for photos here instead: this server fetches each one once, makes it the
size a card needs, keeps it on disk, and browsers keep it too.

Only public addresses are fetched (safe_fetch: no private hosts, every
redirect re-checked), only images are returned, size is capped, and calls
are rate limited.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from PIL import Image

from app.core.config import get_settings
from app.core.logging import logger
from app.core.rate_limit import rate_limiter
from app.services.safe_fetch import UnsafeURLError, check_public_url, fetch_limited

router = APIRouter(prefix="/img", tags=["media"])

_MAX_BYTES = 8 * 1024 * 1024
_WIDTHS = (240, 400, 600, 900)
_CACHE_HEADERS = {"Cache-Control": "public, max-age=604800, immutable"}


def _cache_dir() -> Path:
    path = Path(get_settings().STORAGE_LOCAL_DIR) / "img-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resize(data: bytes, width: int) -> bytes:
    """At most `width` wide, as JPEG (white behind any transparency)."""
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        if img.width > width:
            img.thumbnail((width, width * 4))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.getchannel("A"))
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=84, optimize=True, progressive=True)
        return out.getvalue()


@router.get("", dependencies=[Depends(rate_limiter("image_proxy", limit=3000, window_seconds=3600))])
async def product_image(u: str = Query(min_length=8, max_length=2048), w: int = 600) -> Response:
    width = min(_WIDTHS, key=lambda size: abs(size - w))
    try:
        check_public_url(u)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not an image address we can show") from exc

    cached = _cache_dir() / f"{hashlib.sha256(f'{width}|{u}'.encode()).hexdigest()}.jpg"
    if cached.exists():
        return Response(content=cached.read_bytes(), media_type="image/jpeg", headers=_CACHE_HEADERS)

    try:
        data = await asyncio.to_thread(fetch_limited, u, max_bytes=_MAX_BYTES, timeout=15.0)
        body = await asyncio.to_thread(_resize, data, width)
    except Exception as exc:  # noqa: BLE001 - a bad, missing or too-big image: no picture, never a crash
        logger.info("image_proxy_failed", error=str(exc)[:160])
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not available") from exc
    try:
        cached.write_bytes(body)
    except OSError:
        pass  # showing it matters more than keeping it
    return Response(content=body, media_type="image/jpeg", headers=_CACHE_HEADERS)
