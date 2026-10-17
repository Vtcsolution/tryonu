"""Photos and videos members upload to the community.

Photos go through the normal photo pipeline (any format, HEIC too, resized).
Videos must really be videos (checked by their first bytes, not their name),
at most COMMUNITY_VIDEO_MAX_MB and COMMUNITY_VIDEO_MAX_SECONDS. When ffmpeg is
installed on the server, each video is converted to an H.264 MP4 every browser
plays (iPhones record HEVC, which Chrome can't) and gets a cover picture;
without ffmpeg the video is kept as uploaded.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.logging import logger
from app.services.image_service import optimize_bytes
from app.services.storage_service import get_storage


def _key(user_id: str, ext: str) -> str:
    return f"community/{user_id}/{secrets.token_urlsafe(12)}.{ext}"


async def save_image(user_id: str, raw: bytes) -> tuple[str, int, int]:
    img = await optimize_bytes(raw)
    key = _key(user_id, img.ext)
    get_storage().put(key, img.content, img.content_type)
    return key, img.width, img.height


def video_kind(raw: bytes) -> tuple[str, str] | None:
    """(file extension, content type) from the file's first bytes, or None if it isn't a video we play."""
    head = raw[:64]
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand.startswith(b"qt"):
            return "mov", "video/quicktime"
        return "mp4", "video/mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "webm", "video/webm"
    return None


def _ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, timeout=60, check=False,
    )
    return json.loads(out.stdout or b"{}")


def _transcode(src: Path, dst: Path, poster: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(src),
            "-vf", "scale='min(720,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dst),
        ],
        capture_output=True, timeout=240, check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", "0.5", "-i", str(dst), "-frames:v", "1", "-q:v", "4", str(poster)],
        capture_output=True, timeout=60, check=False,
    )


async def save_video(user_id: str, raw: bytes) -> tuple[str, str | None, int | None, int | None]:
    """(video key, cover picture key or None, width, height)."""
    settings = get_settings()
    if len(raw) > settings.COMMUNITY_VIDEO_MAX_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"That video is too big. Please use one under {settings.COMMUNITY_VIDEO_MAX_MB} MB.",
        )
    kind = video_kind(raw)
    if kind is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That file isn't a video we can play. Try an MP4 or MOV.")
    ext, content_type = kind
    storage = get_storage()
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        key = _key(user_id, ext)
        storage.put(key, raw, content_type)
        return key, None, None, None

    with tempfile.TemporaryDirectory() as tmp:
        src, dst, poster = Path(tmp) / f"in.{ext}", Path(tmp) / "out.mp4", Path(tmp) / "poster.jpg"
        src.write_bytes(raw)
        info = await asyncio.to_thread(_ffprobe, src)
        duration = float((info.get("format") or {}).get("duration") or 0)
        if duration > settings.COMMUNITY_VIDEO_MAX_SECONDS + 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Videos can be up to {settings.COMMUNITY_VIDEO_MAX_SECONDS} seconds. Please trim it and try again.",
            )
        try:
            await asyncio.to_thread(_transcode, src, dst, poster)
        except Exception as exc:  # noqa: BLE001 — keep the original rather than lose the post
            logger.warning("community_video_transcode_failed", error=str(exc)[:200])
            key = _key(user_id, ext)
            storage.put(key, raw, content_type)
            return key, None, None, None
        out_info = await asyncio.to_thread(_ffprobe, dst)
        stream = next((s for s in out_info.get("streams", []) if s.get("codec_type") == "video"), {})
        key = _key(user_id, "mp4")
        storage.put(key, dst.read_bytes(), "video/mp4")
        poster_key = None
        if poster.exists():
            poster_key = _key(user_id, "jpg")
            storage.put(poster_key, poster.read_bytes(), "image/jpeg")
        return key, poster_key, stream.get("width"), stream.get("height")


def delete_files(*keys: str | None) -> None:
    storage = get_storage()
    for key in keys:
        if key:
            try:
                storage.delete(key)
            except Exception:  # noqa: BLE001 — a leftover file is harmless
                pass
