"""An email to the help inbox when the worker stops or try-ons keep failing."""

from __future__ import annotations

from app.email.registry import get_email_provider
from app.services import health_alerts


async def test_a_stopped_worker_is_emailed_once_then_not_again_for_hours(db, monkeypatch):
    monkeypatch.setattr("app.services.queue.queue_state", lambda: {"mode": "redis", "waiting": 2, "workers": 0, "busy": 0})
    health_alerts._last_sent.clear()
    sent = get_email_provider().sent
    before = len(sent)

    assert "worker" in await health_alerts.check_once(db)
    alert = sent[before]
    assert alert["subject"].startswith("TryOnU alert") and "pm2 restart tryonu-worker" in alert["body"]
    assert await health_alerts.check_once(db) == []  # not again for a few hours
    health_alerts._last_sent.clear()


async def test_nothing_is_emailed_when_all_is_well(db, monkeypatch):
    monkeypatch.setattr("app.services.queue.queue_state", lambda: {"mode": "redis", "waiting": 0, "workers": 1, "busy": 0})
    health_alerts._last_sent.clear()
    assert [k for k, _ in await health_alerts.problems(db) if k in ("worker", "stuck", "queue")] == []
