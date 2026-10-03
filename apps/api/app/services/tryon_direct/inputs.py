"""Getting the two input images to FASHN exactly as they are.

Both go out as data URIs of their ORIGINAL bytes — never decoded and
re-encoded — so FASHN sees precisely the stored person photo and precisely
the retailer's product photo. A URL would also work for the product, but
fetching it ourselves means the image is verified to exist, is what we
record, and cannot change between our check and FASHN's fetch. It also
works when storage is local disk, which FASHN could not reach.
"""

from __future__ import annotations

import base64
import io

import httpx
from PIL import Image, UnidentifiedImageError

# FASHN accepts 30 MiB per image; a data URI is a third larger than its bytes
MAX_INPUT_BYTES = 20 * 1024 * 1024
_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}
_UA = "Mozilla/5.0 (compatible; TryOnU/1.0)"


class DirectInputError(Exception):
    """An input image could not be used. Raised before anything is sent to
    FASHN, so it never costs a credit."""


def sniff_mime(data: bytes) -> str:
    """The real image type from the bytes themselves (not a header or file
    name, which a retailer CDN gets wrong)."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format or ""
    except (UnidentifiedImageError, OSError) as exc:
        raise DirectInputError("the file is not a readable image") from exc
    mime = _MIME.get(fmt)
    if mime is None:
        raise DirectInputError(f"unsupported image format: {fmt or 'unknown'}")
    return mime


def to_data_uri(data: bytes) -> str:
    if len(data) > MAX_INPUT_BYTES:
        raise DirectInputError(
            f"image is {len(data) // (1024 * 1024)} MB; the limit is {MAX_INPUT_BYTES // (1024 * 1024)} MB"
        )
    return f"data:{sniff_mime(data)};base64,{base64.b64encode(data).decode()}"


async def fetch_product_image(url: str) -> bytes:
    """The product's listing photo, byte for byte."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": _UA}) as client:
            resp = await client.get(url)
    except httpx.RequestError as exc:
        raise DirectInputError(f"could not download the product image: {type(exc).__name__}") from exc
    if resp.status_code >= 400:
        raise DirectInputError(f"could not download the product image: HTTP {resp.status_code}")
    return resp.content
