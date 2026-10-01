"""Refuses a write against the production database by accident.

The FastAPI app and the RQ worker legitimately write to production in
production — this guard is never wired into either of them. It exists
for the other place a write can happen: a developer running a one-off
script locally (app/scripts/*.py) with a .env whose DATABASE_URL happens
to point at the real Supabase project, the way this repo's own local
.env has all session. A script that writes should call
assert_safe_to_write() before its first write; it raises unless
ALLOW_PROD_WRITES=true is explicitly set for that one run.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from app.core.config import get_settings

# The production Supabase host this project's local .env has pointed at
# all session (confirmed via its own DATABASE_URL). Hostname-based, not a
# full-URL match, so it still catches the production DB regardless of
# which credentials or query params are on the connection string.
PRODUCTION_DB_HOST = "aws-0-ap-southeast-1.pooler.supabase.com"


class ProductionWriteBlocked(RuntimeError):
    pass


def _host_of(database_url: str) -> str:
    # asyncpg's own scheme (postgresql+asyncpg://) isn't a scheme urlparse
    # recognises as having a netloc; normalise it first.
    normalized = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return urlparse(normalized).hostname or ""


def is_production_database(database_url: str | None = None) -> bool:
    url = database_url if database_url is not None else get_settings().DATABASE_URL
    return _host_of(url) == PRODUCTION_DB_HOST


def assert_safe_to_write(database_url: str | None = None) -> None:
    """Call this before a script's first write. Raises ProductionWriteBlocked
    unless the configured DATABASE_URL is not production, or
    ALLOW_PROD_WRITES=true was explicitly set in the environment for this
    run."""
    if not is_production_database(database_url):
        return
    if os.environ.get("ALLOW_PROD_WRITES", "").strip().lower() == "true":
        return
    raise ProductionWriteBlocked(
        f"Refusing to write: DATABASE_URL points at the production database ({PRODUCTION_DB_HOST}). "
        "Set ALLOW_PROD_WRITES=true if this write is really intended."
    )
