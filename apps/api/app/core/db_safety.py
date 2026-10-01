"""Refuses a write against the production database by accident.

The FastAPI app and the RQ worker legitimately write to production in
production — this guard is never wired into either of them. It exists
for a dev-only script (app/scripts/*.py) that writes: call
assert_safe_to_write() before its first write; it raises unless
ALLOW_PROD_WRITES=true is explicitly set for that one run.

What "production" means here: ENV=production (app/core/config.py's own
setting), not a specific guessed DATABASE_URL. An earlier version of this
guard matched a hardcoded Supabase host, on the mistaken belief that was
production — it wasn't (see memory production_db_is_local_postgres_on_vps
for how that was found). Real production's database is local Postgres on
the VPS itself, reachable only from there; matching on ENV instead is
correct everywhere this code runs, VPS or not, and doesn't need updating
every time infrastructure changes.
"""

from __future__ import annotations

import os

from app.core.config import get_settings


class ProductionWriteBlocked(RuntimeError):
    pass


def is_production_environment(env: str | None = None) -> bool:
    return (env if env is not None else get_settings().ENV) == "production"


def assert_safe_to_write(env: str | None = None) -> None:
    """Call this before a script's first write. Raises ProductionWriteBlocked
    when ENV=production, unless ALLOW_PROD_WRITES=true was explicitly set
    in the environment for this run."""
    if not is_production_environment(env):
        return
    if os.environ.get("ALLOW_PROD_WRITES", "").strip().lower() == "true":
        return
    raise ProductionWriteBlocked(
        "Refusing to write: ENV=production. Set ALLOW_PROD_WRITES=true if this write is really intended."
    )
