"""Upload validation + optimization.

Every uploaded image is re-encoded from decoded pixels (never the original
bytes are trusted or stored as-is) — this both strips EXIF/GPS metadata and
neutralises polyglot-file attacks (an image whose bytes are also valid
HTML/JS). Oversized images are downscaled before storage.

Orientation is applied BEFORE that strip, never after: a phone's portrait
photo is usually stored as landscape pixels plus an EXIF rotation tag, and
stripping metadata without reading that tag first throws away the one
thing that could ever correct it — permanently, since nothing downstream
(cv2.imdecode included) reads EXIF either. Every try-on pipeline then
treats a sideways photo as the real one.
"""

from __future__ import annotations

import io

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings

settings = get_settings()

try:  # iPhone photos arrive as HEIC/HEIF
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover — decoder not installed: HEIC uploads fail as "not a valid image"
    pass

MAX_DIMENSION = 2048


class ProcessedImage:
    __slots__ = ("content", "content_type", "width", "height", "ext")

    def __init__(self, content: bytes, content_type: str, width: int, height: int, ext: str) -> None:
        self.content = content
        self.content_type = content_type
        self.width = width
        self.height = height
        self.ext = ext


async def validate_and_optimize(file: UploadFile) -> ProcessedImage:
    # The browser's declared type is not trusted either way: live, a normal JPEG
    # was refused with 415 because the browser labelled it differently. Any file
    # Pillow can actually decode is accepted; anything else fails below as
    # "not a valid image".
    raw = await file.read()
    if len(raw) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large — max {settings.MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
        )
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()  # cheap structural check
        img = Image.open(io.BytesIO(raw))  # re-open: verify() consumes the parser
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File is not a valid image"
        ) from exc

    # Read the EXIF orientation tag and actually rotate the pixels by it
    # before anything below discards that tag for good.
    img = ImageOps.exif_transpose(img)

    # normalise mode, strip metadata by rebuilding a fresh image buffer
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88, optimize=True)
    content = out.getvalue()

    return ProcessedImage(
        content=content,
        content_type="image/jpeg",
        width=img.width,
        height=img.height,
        ext="jpg",
    )
