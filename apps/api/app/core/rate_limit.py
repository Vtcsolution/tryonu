"""Sliding-window rate limiting.

Uses Redis (INCR + EXPIRE) when REDIS_URL is configured — safe across
multiple API replicas. Falls back to an in-process counter for local dev,
which is fine for a single-process `uvicorn` but is *not* multi-instance
safe — production must set REDIS_URL.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

settings = get_settings()

_local_buckets: dict[str, list[float]] = defaultdict(list)
_redis_client = None


def _get_redis():  # noqa: ANN201
    global _redis_client
    if _redis_client is None and settings.REDIS_URL:
        import redis

        _redis_client = redis.from_url(settings.REDIS_URL)
    return _redis_client


def _client_key(request: Request) -> str:
    user = getattr(request.state, "user_id", None)
    if user:
        return f"user:{user}"
    fwd = request.headers.get("x-forwarded-for")
    ip = (fwd.split(",")[0].strip() if fwd else None) or (
        request.client.host if request.client else "unknown"
    )
    return f"ip:{ip}"


def check_rate_limit(request: Request, *, bucket: str, limit: int, window_seconds: int) -> None:
    key = f"ratelimit:{bucket}:{_client_key(request)}"
    now = time.time()

    r = _get_redis()
    if r is not None:
        pipe = r.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
    else:
        window = _local_buckets[key]
        cutoff = now - window_seconds
        while window and window[0] < cutoff:
            window.pop(0)
        window.append(now)
        count = len(window)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit} per {window_seconds}s). Try again shortly.",
        )


def rate_limiter(bucket: str, limit: int, window_seconds: int = 60):
    """FastAPI dependency factory: Depends(rate_limiter('tryon', 30, 3600))."""

    async def _dep(request: Request) -> None:
        check_rate_limit(request, bucket=bucket, limit=limit, window_seconds=window_seconds)

    return _dep
