"""Serves local-disk storage in dev, gated by the same HMAC signature a real
presigned S3/R2 URL would carry (see services/storage_service.py). Not
mounted at all when S3 is configured — production traffic never touches
this route, it goes straight to the CDN/S3 presigned URL.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.services.storage_service import local_storage_root, verify_local_signature

router = APIRouter(tags=["media"])


@router.get("/media/{key:path}")
async def serve_media(key: str, exp: int = Query(...), sig: str = Query(...)):
    if not verify_local_signature(key, exp, sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Link expired or invalid")

    path = (local_storage_root() / key).resolve()
    root = local_storage_root().resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return FileResponse(path)
