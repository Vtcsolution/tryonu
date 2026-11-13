"""Short emails to TryOnU's own inbox when something needs a person: a new
store, a new developer account, a store order, a payment. Sent in the
background, so a slow mail server never slows the shopper down; a failure
is logged, never shown to them."""

from __future__ import annotations

import asyncio
from typing import Literal

from app.core.config import get_settings
from app.core.logging import logger
from app.email.registry import get_email_provider
from app.email.templates import site_url

Inbox = Literal["support", "sales", "billing"]

_tasks: set[asyncio.Task] = set()


def _address(inbox: Inbox) -> str | None:
    s = get_settings()
    return {"support": s.SUPPORT_EMAIL, "sales": s.SALES_EMAIL, "billing": s.BILLING_EMAIL}[inbox] or s.SUPPORT_EMAIL or None


async def _send(to: str, subject: str, body: str, reply_to: str | None) -> None:
    try:
        await get_email_provider().send(to=to, subject=subject, text_body=body, reply_to=reply_to)
    except Exception as exc:  # noqa: BLE001
        logger.warning("team_alert_failed", subject=subject[:80], error=str(exc)[:200])


def tell_team(inbox: Inbox, subject: str, lines: list[str], *, admin_path: str | None = None, reply_to: str | None = None) -> None:
    to = _address(inbox)
    if not to:
        return
    body = "\n".join(lines + ([f"\nOpen in the admin: {site_url(admin_path)}"] if admin_path else []))
    task = asyncio.create_task(_send(to, f"TryOnU: {subject}", body, reply_to))
    _tasks.add(task)  # kept until done, so it isn't garbage-collected mid-send
    task.add_done_callback(_tasks.discard)
