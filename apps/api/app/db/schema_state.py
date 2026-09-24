"""Is the database schema the one this code expects?

Deploying code without running its migrations is an easy mistake and an
expensive one: every query touching a new column raises, which surfaces
to a browser as a 500 (and, before the CORS fix, as a phantom CORS
error). This answers the question directly, so /health can say it out
loud instead of leaving it to be inferred from a stack trace.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy import text

from app.core.logging import logger
from app.db.session import AsyncSessionLocal


@lru_cache(maxsize=1)
def expected_revision() -> str | None:
    """The head revision in this checkout's migration scripts."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        root = Path(__file__).resolve().parents[2]  # apps/api
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        heads = ScriptDirectory.from_config(config).get_heads()
        return heads[0] if len(heads) == 1 else ",".join(sorted(heads))
    except Exception as exc:  # noqa: BLE001 — never let a health check fail
        logger.warning("schema_state_unknown_head", error=str(exc)[:200])
        return None


@lru_cache(maxsize=1)
def _known_revisions() -> frozenset[str]:
    """Every revision this checkout's migration scripts know about."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        root = Path(__file__).resolve().parents[2]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        return frozenset(script.revision for script in ScriptDirectory.from_config(config).walk_revisions())
    except Exception:  # noqa: BLE001 — never let a health check fail
        return frozenset()


async def applied_revision() -> str | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("select version_num from alembic_version"))
        rows = [r[0] for r in result.all()]
    return rows[0] if len(rows) == 1 else (",".join(sorted(rows)) if rows else None)


async def schema_status() -> dict:
    """{"state": ok | behind | unknown, ...} — `behind` means migrations
    are pending and things will fail in ways that look unrelated."""
    expected = expected_revision()
    try:
        applied = await applied_revision()
    except Exception as exc:  # noqa: BLE001 — a missing table is itself the answer
        return {"state": "unknown", "expected": expected, "error": str(exc)[:120]}

    if expected is None or applied is None:
        return {"state": "unknown", "expected": expected, "applied": applied}
    if applied == expected:
        return {"state": "ok", "revision": applied}
    # Which way round matters. A database the code doesn't recognise means
    # this process is running older code than the checkout it was deployed
    # from — almost always a pull without a restart, and it reads as
    # "behind" unless it is spelled out.
    if applied not in _known_revisions():
        return {
            "state": "ahead",
            "applied": applied,
            "expected": expected,
            "fix": "the database is newer than this process — restart it: pm2 restart tryonu-api tryonu-worker",
        }
    return {
        "state": "behind",
        "applied": applied,
        "expected": expected,
        "fix": "run: cd apps/api && ./.venv/bin/python -m alembic upgrade head",
    }
