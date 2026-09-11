"""Timezone helpers.

PostgreSQL round-trips `DateTime(timezone=True)` values with tzinfo intact;
SQLite does not (it has no native timestamp-with-timezone type — see
db/session.py's dialect notes), so a value read back from SQLite comes back
naive even though everything this app writes is UTC. `as_aware()` closes
that gap wherever a DB-loaded datetime is compared against a fresh
`utcnow()` — comparing naive and aware datetimes otherwise raises TypeError
on SQLite while working by accident on Postgres.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(dt: datetime | None) -> datetime | None:
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)
