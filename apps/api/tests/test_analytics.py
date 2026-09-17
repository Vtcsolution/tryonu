"""Visitor analytics: collection rules (bots/admin pages excluded, no IP
stored, durations only from the creating browser) and the admin report."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy import delete, inspect, select
from starlette.requests import Request

from app.models.analytics import PageView
from app.services.analytics_service import classify_user_agent, client_ip, country_for_ip, referrer_host
from tests.conftest import make_admin, register_and_login

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
WIN_EDGE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 Edg/124.0"
ANDROID_TABLET = "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MAC_CHROME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


@pytest_asyncio.fixture(autouse=True)
async def _clean_page_views(db):
    await db.execute(delete(PageView))
    await db.commit()
    yield


def _view(path="/try", visitor="visitor-aaaa-1", session="session-aaaa-1", referrer=None):
    body = {"path": path, "visitor_id": visitor, "session_id": session}
    if referrer:
        body["referrer"] = referrer
    return body


async def _post(client, body, ua=IPHONE, country=None):
    headers = {"user-agent": ua}
    if country:
        headers["cf-ipcountry"] = country
    return await client.post("/api/v1/analytics/pageview", json=body, headers=headers)


@pytest.mark.parametrize(
    ("ua", "expected"),
    [
        (IPHONE, ("mobile", "Safari", "iOS")),
        (WIN_EDGE, ("desktop", "Edge", "Windows")),
        (ANDROID_TABLET, ("tablet", "Chrome", "Android")),
        (MAC_CHROME, ("desktop", "Chrome", "macOS")),
    ],
)
def test_classify_user_agent(ua, expected):
    assert classify_user_agent(ua) == expected


def test_client_ip_ignores_spoofable_leftmost_forwarded_for():
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"6.6.6.6, 203.0.113.9")],
        "client": ("127.0.0.1", 1234),
    }
    assert client_ip(Request(scope)) == "203.0.113.9"


def test_private_ips_and_missing_db_give_no_country():
    assert country_for_ip("10.0.0.5") is None
    assert country_for_ip("not-an-ip") is None
    assert country_for_ip("8.8.8.8") is None  # no GeoIP db in the test env


def test_referrer_host_keeps_external_sources_only():
    assert referrer_host("https://www.google.com/search?q=x") == "google.com"
    assert referrer_host("http://localhost:3000/try") is None  # our own site
    assert referrer_host("") is None


async def test_pageview_records_visit_without_storing_ip(client, db):
    resp = await _post(client, _view(path="/try?utm_source=x#top", referrer="https://instagram.com/p/1"), country="PK")
    assert resp.status_code == 201, resp.text

    view = (await db.execute(select(PageView))).scalar_one()
    assert view.path == "/try"
    assert (view.device, view.browser, view.os, view.country) == ("mobile", "Safari", "iOS", "PK")
    assert view.referrer_host == "instagram.com"
    assert not any("ip" in c.key for c in inspect(PageView).columns)


async def test_bots_and_admin_pages_are_not_recorded(client, db):
    assert (await _post(client, _view(), ua=GOOGLEBOT)).status_code == 204
    assert (await _post(client, _view(path="/admin"))).status_code == 204
    assert (await _post(client, _view(path="/admin/users"))).status_code == 204
    assert (await db.execute(select(PageView))).scalars().first() is None


async def test_invalid_ids_are_rejected(client):
    assert (await _post(client, _view(visitor="x"))).status_code == 422
    assert (await _post(client, _view(session="has spaces in it"))).status_code == 422


async def test_signed_in_visit_is_attributed_to_the_user(client, db):
    data = await register_and_login(client)
    await _post(client, _view())
    view = (await db.execute(select(PageView))).scalar_one()
    assert view.user_id == data["user"]["id"]


async def test_duration_beacon_only_from_creating_browser_keeps_max_and_clamps(client, db):
    view_id = (await _post(client, _view(visitor="visitor-owner-1"))).json()["id"]
    url = f"/api/v1/analytics/pageview/{view_id}/duration"
    beacon = lambda visitor, ms: client.post(  # noqa: E731
        url, content=json.dumps({"visitor_id": visitor, "duration_ms": ms}), headers={"content-type": "text/plain"}
    )

    assert (await beacon("visitor-owner-1", 12_000)).status_code == 204
    assert (await beacon("visitor-owner-1", 4_000)).status_code == 204  # later, shorter beacon
    assert (await beacon("visitor-someone-else", 999_000)).status_code == 204  # ignored
    view = (await db.execute(select(PageView))).scalar_one()
    await db.refresh(view)
    assert view.duration_ms == 12_000

    await beacon("visitor-owner-1", 10 * 60 * 60 * 1000)
    await db.refresh(view)
    assert view.duration_ms == 30 * 60 * 1000

    assert (await client.post(url, content="not json", headers={"content-type": "text/plain"})).status_code == 400


async def test_admin_report_is_admin_only(client):
    await register_and_login(client)
    assert (await client.get("/api/v1/admin/analytics")).status_code == 403


async def test_admin_report_aggregates_visitors_countries_devices_pages(client, db):
    # visitor A (Pakistan, iPhone): 2 pages in one session
    a1 = (await _post(client, _view(path="/", visitor="visitor-a-1234", session="session-a-1234", referrer="https://google.com"), country="PK")).json()["id"]
    await _post(client, _view(path="/try", visitor="visitor-a-1234", session="session-a-1234"), country="PK")
    # visitor B (UAE, Windows): 1 page — a bounce
    await _post(client, _view(path="/", visitor="visitor-b-1234", session="session-b-1234"), ua=WIN_EDGE, country="AE")
    await client.post(
        f"/api/v1/analytics/pageview/{a1}/duration",
        content=json.dumps({"visitor_id": "visitor-a-1234", "duration_ms": 30_000}),
        headers={"content-type": "text/plain"},
    )

    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])
    resp = await client.get("/api/v1/admin/analytics", params={"days": 7})
    assert resp.status_code == 200, resp.text
    r = resp.json()

    assert (r["views"], r["visitors"], r["sessions"]) == (3, 2, 2)
    assert r["live_visitors"] == 2
    assert r["bounce_rate"] == 0.5
    assert r["pages_per_session"] == 1.5
    assert r["avg_duration_ms"] == 30_000
    assert len(r["daily"]) == 7 and r["daily"][-1]["views"] == 3

    countries = {c["key"]: (c["visitors"], c["views"]) for c in r["countries"]}
    assert countries == {"PK": (1, 2), "AE": (1, 1)}
    assert {d["key"] for d in r["devices"]} == {"mobile", "desktop"}
    home = next(p for p in r["pages"] if p["path"] == "/")
    assert (home["views"], home["visitors"], home["avg_duration_ms"]) == (2, 2, 30_000)
    assert r["referrers"] == [{"key": "google.com", "visitors": 1, "views": 1}]
