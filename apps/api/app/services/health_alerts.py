"""An email to the help inbox when something is wrong, before customers say so:

- no try-on worker is running (every try-on would wait forever)
- try-ons are waiting in the queue and none starts
- most try-ons in the last hour failed
- the server's disk is nearly full

Checked every few minutes from the API; each problem is emailed at most once
every few hours. (The whole server being down can't email from itself: an
outside checker such as UptimeRobot watches /health for that.)"""

from __future__ import annotations

import asyncio
import shutil
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.models.enums import JobStatus
from app.models.tryon import TryOnJob

CHECK_EVERY_SECONDS = 5 * 60
REPEAT_AFTER_SECONDS = 3 * 3600
_last_sent: dict[str, float] = {}


async def problems(db: AsyncSession) -> list[tuple[str, str]]:
    """(kind, plain words) for every problem right now."""
    from app.services.queue import queue_state

    found: list[tuple[str, str]] = []
    q = await asyncio.to_thread(queue_state)
    if q.get("mode") == "redis":
        if "error" in q:
            found.append(("queue", f"The try-on queue (Redis) can't be reached: {q['error']}"))
        elif q.get("workers", 0) == 0:
            found.append(("worker", "No try-on worker is running, so every try-on waits. On the server: pm2 restart tryonu-worker"))
        elif q.get("waiting", 0) >= 5 and q.get("busy", 0) == 0:
            found.append(("stuck", f"{q['waiting']} try-ons are waiting and the worker isn't taking them. On the server: pm2 restart tryonu-worker"))

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    rows = dict(
        (
            await db.execute(
                select(TryOnJob.status, func.count())
                .where(TryOnJob.created_at >= since, TryOnJob.status.in_((JobStatus.COMPLETED, JobStatus.FAILED)))
                .group_by(TryOnJob.status)
            )
        ).all()
    )
    failed, done = int(rows.get(JobStatus.FAILED, 0)), int(rows.get(JobStatus.COMPLETED, 0))
    if failed >= 3 and failed > done:
        found.append(("failing", f"{failed} of {failed + done} try-ons in the last hour failed. Admin → Try-ons shows why."))

    usage = shutil.disk_usage("/")
    if usage.free / usage.total < 0.10:
        found.append(("disk", f"The server's disk is {100 - usage.free * 100 // usage.total}% full ({usage.free // 2**30} GB left)."))
    return found


async def check_once(db: AsyncSession) -> list[str]:
    """Emails the problems not emailed in the last few hours; returns their kinds."""
    from app.email.registry import get_email_provider
    from app.email.templates import action_email, site_url

    now = time.monotonic()
    fresh = [(k, t) for k, t in await problems(db) if now - _last_sent.get(k, -REPEAT_AFTER_SECONDS) >= REPEAT_AFTER_SECONDS]
    if not fresh:
        return []
    to = get_settings().SUPPORT_EMAIL
    text, page = action_email(
        "Something needs a look on TryOnU",
        [t for _, t in fresh],
        "Open the admin panel",
        site_url("/admin/dashboard#system"),
        after=["You'll get this again in a few hours if it's still happening."],
    )
    try:
        await get_email_provider().send(to=to, subject="TryOnU alert: " + fresh[0][1][:80], text_body=text, html_body=page)
    except Exception as exc:  # noqa: BLE001 - logged; tried again next round
        logger.error("health_alert_email_failed", error=str(exc)[:200], problems=[k for k, _ in fresh])
        return []
    for k, _ in fresh:
        _last_sent[k] = now
    logger.warning("health_alert_sent", problems=[k for k, _ in fresh])
    return [k for k, _ in fresh]


async def check_forever() -> None:
    """Runs for the life of the API process."""
    from app.db.session import AsyncSessionLocal

    await asyncio.sleep(180)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await check_once(db)
        except Exception as exc:  # noqa: BLE001 - never let the loop die
            logger.warning("health_check_failed", error=str(exc)[:200])
        await asyncio.sleep(CHECK_EVERY_SECONDS)
