"""Serves local-disk storage in dev, gated by the same HMAC signature a real
presigned S3/R2 URL would carry (see services/storage_service.py). Not
mounted at all when S3 is configured — production traffic never touches
this route, it goes straight to the CDN/S3 presigned URL.
"""

from __future__ import annotations

import asyncio
import hashlib

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, Response

from app.services.storage_service import local_storage_root, verify_local_signature

router = APIRouter(tags=["media"])


@router.get("/media/{key:path}")
async def serve_media(key: str, exp: int = Query(...), sig: str = Query(...), w: int | None = None):
    if not verify_local_signature(key, exp, sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Link expired or invalid")

    path = (local_storage_root() / key).resolve()
    root = local_storage_root().resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    # ?w=240: a small copy for thumbnail strips. A full try-on picture is
    # several MB, and a row of them showed only half-loaded strips.
    if w in _THUMB_WIDTHS and path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        from app.api.v1.endpoints.image_proxy import _cache_dir, _resize

        cached = _cache_dir() / f"media-{hashlib.sha256(f'{w}|{key}'.encode()).hexdigest()}.jpg"
        if not cached.is_file():
            data = await asyncio.to_thread(path.read_bytes)
            cached.write_bytes(await asyncio.to_thread(_resize, data, w))
        return Response(content=cached.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
    return FileResponse(path)


_THUMB_WIDTHS = (240, 400, 600, 900)
