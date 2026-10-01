"""Per-job debug image capture: every intermediate stage of a render
(input, each provider output, after alignment, after keep_person, after
each paste-back, the masks used) saved under a private storage prefix, so
a seam/ghost/patch bug can be read back stage by stage afterward instead
of guessed at from the final image alone.

Off by default (TRYON_SAVE_DEBUG), and even when on, only ever for the
accounts listed in TRYON_DEBUG_USER_EMAILS — production users' photos are
private, and nothing here is allowed to capture them. Saved files are
auto-deleted after TRYON_DEBUG_RETENTION_DAYS by sweep_debug_forever(),
the same "runs for the life of the API process" pattern as
app.services.stuck_jobs.sweep_forever.
"""

from __future__ import annotations

import asyncio
import time

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.logging import logger
from app.services.storage_service import get_storage

DEBUG_PREFIX = "debug/tryon"


def is_debug_enabled(user_email: str | None) -> bool:
    settings = get_settings()
    if not settings.TRYON_SAVE_DEBUG or not user_email:
        return False
    allowed = {e.strip().lower() for e in settings.TRYON_DEBUG_USER_EMAILS.split(",") if e.strip()}
    return user_email.strip().lower() in allowed


class DebugCapture:
    """One instance per job. save() no-ops (and never raises) unless this
    job's account is on the debug allowlist, so call sites along the
    render path never need their own enabled-check."""

    def __init__(self, job_id: str, user_email: str | None) -> None:
        self.job_id = job_id
        self.enabled = is_debug_enabled(user_email)
        self._seq = 0

    def save(self, stage: str, image: bytes | np.ndarray, label: str = "") -> None:
        if not self.enabled:
            return
        try:
            content = bytes(image) if isinstance(image, (bytes, bytearray)) else _encode_png(image)
            self._seq += 1
            suffix = f"_{label}" if label else ""
            key = f"{DEBUG_PREFIX}/{self.job_id}/{self._seq:02d}_{stage}{suffix}.png"
            get_storage().put(key, content, "image/png")
        except Exception as exc:  # noqa: BLE001 — debug capture must never break a real render
            logger.warning("tryon_debug_capture_failed", job_id=self.job_id, stage=stage, error=str(exc)[:200])


def _encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("could not encode debug image")
    return buf.tobytes()


async def sweep_debug_artifacts() -> int:
    """Delete debug images older than TRYON_DEBUG_RETENTION_DAYS. Debug
    saving is only ever for test accounts, but nothing kept forever is
    really "temporary" — this is the auto-delete half of that promise."""
    settings = get_settings()
    cutoff = time.time() - settings.TRYON_DEBUG_RETENTION_DAYS * 86400
    storage = get_storage()
    entries = await asyncio.to_thread(storage.list_with_mtime, DEBUG_PREFIX)
    deleted = 0
    for key, mtime in entries:
        if mtime < cutoff:
            await asyncio.to_thread(storage.delete, key)
            deleted += 1
    return deleted


DEBUG_SWEEP_EVERY_SECONDS = 3600


async def sweep_debug_forever() -> None:
    """Runs for the life of the API process — only ever started when
    TRYON_SAVE_DEBUG is on (see app/main.py), so it costs nothing when
    debug capture is off."""
    while True:
        await asyncio.sleep(DEBUG_SWEEP_EVERY_SECONDS)
        try:
            deleted = await sweep_debug_artifacts()
            if deleted:
                logger.info("tryon_debug_artifacts_swept", count=deleted)
        except Exception as exc:  # noqa: BLE001 — a sweep must never end the loop
            logger.warning("tryon_debug_sweep_failed", error=str(exc)[:200])
