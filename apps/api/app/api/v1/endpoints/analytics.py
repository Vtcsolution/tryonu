"""Visitor analytics: public page-view collection + the admin report."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import distinct, func, select

from app.core.deps import AdminUser, DbSession, OptionalUser
from app.core.rate_limit import rate_limiter
from app.models.analytics import PageView
from app.services.analytics_service import (
    classify_user_agent,
    country_for_request,
    geoip_available,
    is_bot,
    normalize_path,
    referrer_host,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
admin_router = APIRouter(prefix="/admin/analytics", tags=["admin"])

_MAX_DURATION_MS = 30 * 60 * 1000
_ID_PATTERN = r"^[A-Za-z0-9-]{8,64}$"


class PageViewIn(BaseModel):
    path: str = Field(max_length=2048)
    referrer: str | None = Field(default=None, max_length=2048)
    visitor_id: str = Field(pattern=_ID_PATTERN)
    session_id: str = Field(pattern=_ID_PATTERN)


class PageViewCreated(BaseModel):
    id: str


class DurationIn(BaseModel):
    visitor_id: str = Field(pattern=_ID_PATTERN)
    duration_ms: int = Field(ge=0)


@router.post(
    "/pageview",
    response_model=PageViewCreated | None,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("analytics_pageview", limit=120, window_seconds=60))],
)
async def record_pageview(payload: PageViewIn, request: Request, db: DbSession, user: OptionalUser):
    ua = request.headers.get("user-agent", "")
    path = normalize_path(payload.path)
    # admin pages would drown out real visitor traffic; bots aren't visitors
    if path is None or path.startswith("/admin") or is_bot(ua):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    device, browser, os_name = classify_user_agent(ua)
    view = PageView(
        visitor_id=payload.visitor_id,
        session_id=payload.session_id,
        user_id=user.id if user else None,
        path=path,
        referrer_host=referrer_host(payload.referrer),
        country=country_for_request(request),
        device=device,
        browser=browser,
        os=os_name,
    )
    db.add(view)
    await db.commit()
    return PageViewCreated(id=view.id)


@router.post(
    "/pageview/{view_id}/duration",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limiter("analytics_duration", limit=240, window_seconds=60))],
)
async def record_duration(view_id: str, request: Request, db: DbSession):
    # sent with navigator.sendBeacon as text/plain (a CORS "simple" request,
    # so it still arrives while the page is unloading), hence manual parsing
    try:
        payload = DurationIn.model_validate(json.loads(await request.body()))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid duration payload") from exc

    view = await db.get(PageView, view_id)
    # only the browser that created the view may report its duration
    if view is None or view.visitor_id != payload.visitor_id:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    duration = min(payload.duration_ms, _MAX_DURATION_MS)
    # beacons can arrive more than once (tab hidden, then closed) — keep the longest
    if view.duration_ms is None or duration > view.duration_ms:
        view.duration_ms = duration
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ admin report


class Breakdown(BaseModel):
    key: str
    visitors: int
    views: int


class PageRow(BaseModel):
    path: str
    views: int
    visitors: int
    avg_duration_ms: int | None


class DayRow(BaseModel):
    date: str
    views: int
    visitors: int


class AnalyticsReport(BaseModel):
    days: int
    geoip_available: bool
    views: int
    visitors: int
    sessions: int
    signed_in_visitors: int
    live_visitors: int
    avg_duration_ms: int | None
    bounce_rate: float | None
    pages_per_session: float | None
    daily: list[DayRow]
    countries: list[Breakdown]
    devices: list[Breakdown]
    browsers: list[Breakdown]
    operating_systems: list[Breakdown]
    referrers: list[Breakdown]
    pages: list[PageRow]


async def _breakdown(db: DbSession, column, since: datetime, limit: int) -> list[Breakdown]:  # noqa: ANN001
    visitors = func.count(distinct(PageView.visitor_id))
    rows = await db.execute(
        select(column, visitors, func.count(PageView.id))
        .where(PageView.created_at >= since)
        .group_by(column)
        .order_by(visitors.desc(), func.count(PageView.id).desc())
        .limit(limit)
    )
    return [Breakdown(key=k if k is not None else "unknown", visitors=v, views=n) for k, v, n in rows.all()]


@admin_router.get("", response_model=AnalyticsReport)
async def analytics_report(_: AdminUser, db: DbSession, days: int = Query(default=7, ge=1, le=365)):
    now = datetime.now(timezone.utc)
    # whole UTC days (today + the previous days-1), so totals and the daily
    # chart always cover exactly the same window
    start = date.fromordinal(now.date().toordinal() - days + 1)
    since = datetime.combine(start, time.min, tzinfo=timezone.utc)
    in_range = PageView.created_at >= since

    views, visitors, sessions, signed_in, avg_duration = (
        await db.execute(
            select(
                func.count(PageView.id),
                func.count(distinct(PageView.visitor_id)),
                func.count(distinct(PageView.session_id)),
                func.count(distinct(PageView.user_id)),
                func.avg(PageView.duration_ms),
            ).where(in_range)
        )
    ).one()

    live = (
        await db.execute(
            select(func.count(distinct(PageView.visitor_id))).where(PageView.created_at >= now - timedelta(minutes=5))
        )
    ).scalar_one()

    per_session = select(func.count(PageView.id).label("n")).where(in_range).group_by(PageView.session_id).subquery()
    single_page_sessions = (
        await db.execute(select(func.count()).select_from(per_session).where(per_session.c.n == 1))
    ).scalar_one()

    day = func.date(PageView.created_at)
    daily_rows = {
        str(d): (n, v)
        for d, n, v in (
            await db.execute(
                select(day, func.count(PageView.id), func.count(distinct(PageView.visitor_id)))
                .where(in_range)
                .group_by(day)
            )
        ).all()
    }
    daily = []
    for offset in range(days):
        d = date.fromordinal(start.toordinal() + offset).isoformat()
        n, v = daily_rows.get(d, (0, 0))
        daily.append(DayRow(date=d, views=n, visitors=v))

    page_visitors = func.count(distinct(PageView.visitor_id))
    page_rows = await db.execute(
        select(PageView.path, func.count(PageView.id), page_visitors, func.avg(PageView.duration_ms))
        .where(in_range)
        .group_by(PageView.path)
        .order_by(func.count(PageView.id).desc())
        .limit(50)
    )

    referrer_rows = await db.execute(
        select(PageView.referrer_host, func.count(distinct(PageView.visitor_id)), func.count(PageView.id))
        .where(in_range, PageView.referrer_host.is_not(None))
        .group_by(PageView.referrer_host)
        .order_by(func.count(distinct(PageView.visitor_id)).desc())
        .limit(20)
    )

    return AnalyticsReport(
        days=days,
        geoip_available=geoip_available(),
        views=views,
        visitors=visitors,
        sessions=sessions,
        signed_in_visitors=signed_in,
        live_visitors=live,
        avg_duration_ms=round(avg_duration) if avg_duration is not None else None,
        bounce_rate=round(single_page_sessions / sessions, 4) if sessions else None,
        pages_per_session=round(views / sessions, 2) if sessions else None,
        daily=daily,
        countries=await _breakdown(db, PageView.country, since, 60),
        devices=await _breakdown(db, PageView.device, since, 5),
        browsers=await _breakdown(db, PageView.browser, since, 10),
        operating_systems=await _breakdown(db, PageView.os, since, 10),
        referrers=[Breakdown(key=k, visitors=v, views=n) for k, v, n in referrer_rows.all()],
        pages=[
            PageRow(path=p, views=n, visitors=v, avg_duration_ms=round(a) if a is not None else None)
            for p, n, v, a in page_rows.all()
        ],
    )
