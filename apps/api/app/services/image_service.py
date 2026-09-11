"""Upload validation + optimization.

Every uploaded image is re-encoded from decoded pixels (never the original
bytes are trusted or stored as-is) — this both strips EXIF/GPS metadata and
neutralises polyglot-file attacks (an image whose bytes are also valid
HTML/JS). Oversized images are downscaled before storage.
"""

from __future__ import annotations

import io

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

settings = get_settings()

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
    if file.content_type not in settings.ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}",
        )

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
