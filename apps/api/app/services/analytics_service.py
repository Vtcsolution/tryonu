"""First-party visitor analytics helpers: country lookup from a local
GeoIP database, user-agent classification, and the real client IP behind
nginx / Cloudflare. No visitor IP is ever stored or sent anywhere."""

from __future__ import annotations

import gzip
import ipaddress
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import Request

from app.core.config import get_settings
from app.core.logging import logger

_reader = None
_reader_path: str | None = None

_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|preview|headless|lighthouse|pingdom|uptime|monitor|curl|wget|python-|httpx|axios|facebookexternalhit|embedly",
    re.I,
)


def geoip_path() -> Path:
    return Path(get_settings().GEOIP_DB_PATH)


def geoip_available() -> bool:
    return geoip_path().is_file()


def _get_reader():  # noqa: ANN202
    global _reader, _reader_path
    path = geoip_path()
    if not path.is_file():
        return None
    if _reader is None or _reader_path != str(path):
        import maxminddb

        _reader = maxminddb.open_database(str(path))
        _reader_path = str(path)
    return _reader


def country_for_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if addr.is_private or addr.is_loopback or addr.is_reserved:
        return None
    reader = _get_reader()
    if reader is None:
        return None
    try:
        record = reader.get(ip)
    except Exception:  # noqa: BLE001 — a corrupt/partial db must never break a page view
        return None
    code = (record or {}).get("country", {}).get("iso_code")
    return code.upper() if isinstance(code, str) and len(code) == 2 else None


def client_ip(request: Request) -> str | None:
    """Cloudflare's header, then nginx's X-Real-IP, then the entry nginx
    itself appended to X-Forwarded-For (the right-most one — the left-most
    can be set by the client and spoofed)."""
    for header in ("cf-connecting-ip", "x-real-ip"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else None


def country_for_request(request: Request) -> str | None:
    cf = request.headers.get("cf-ipcountry", "").upper()
    if len(cf) == 2 and cf not in ("XX", "T1"):
        return cf
    return country_for_ip(client_ip(request))


def is_bot(user_agent: str) -> bool:
    return not user_agent or bool(_BOT_RE.search(user_agent))


def classify_user_agent(ua: str) -> tuple[str, str, str]:
    """(device, browser, os) — coarse families are all the dashboard needs."""
    low = ua.lower()

    if "ipad" in low or "tablet" in low or ("android" in low and "mobile" not in low):
        device = "tablet"
    elif "mobi" in low or "iphone" in low or "ipod" in low:
        device = "mobile"
    else:
        device = "desktop"

    if "edg/" in low or "edga/" in low or "edgios/" in low:
        browser = "Edge"
    elif "opr/" in low or "opera" in low:
        browser = "Opera"
    elif "samsungbrowser" in low:
        browser = "Samsung Internet"
    elif "firefox" in low or "fxios" in low:
        browser = "Firefox"
    elif "chrome" in low or "crios" in low:
        browser = "Chrome"
    elif "safari" in low:
        browser = "Safari"
    else:
        browser = "Other"

    if "windows" in low:
        os_name = "Windows"
    elif "iphone" in low or "ipad" in low or "ipod" in low:
        os_name = "iOS"
    elif "android" in low:
        os_name = "Android"
    elif "mac os" in low or "macintosh" in low:
        os_name = "macOS"
    elif "cros" in low:
        os_name = "ChromeOS"
    elif "linux" in low:
        os_name = "Linux"
    else:
        os_name = "Other"

    return device, browser, os_name


def referrer_host(referrer: str | None) -> str | None:
    """External referring site only — internal navigation isn't a source."""
    if not referrer:
        return None
    host = (urlparse(referrer).hostname or "").lower()
    if not host:
        return None
    own = (urlparse(str(get_settings().FRONTEND_URL)).hostname or "").lower()
    if host == own or host.removeprefix("www.") == own.removeprefix("www."):
        return None
    return host.removeprefix("www.")[:255]


def normalize_path(path: str) -> str | None:
    path = path.split("?", 1)[0].split("#", 1)[0].strip()
    if not path.startswith("/") or len(path) > 512:
        return None
    return path.rstrip("/") or "/"


async def download_geoip_db() -> bool:
    """Fetches this month's DB-IP country lite file (falls back to last
    month's early in the month, before the new one is published)."""
    target = geoip_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    months = [now.strftime("%Y-%m")]
    prev = now.replace(day=1)
    prev = prev.replace(year=prev.year - 1, month=12) if prev.month == 1 else prev.replace(month=prev.month - 1)
    months.append(prev.strftime("%Y-%m"))

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        for month in months:
            url = f"https://download.db-ip.com/free/dbip-country-lite-{month}.mmdb.gz"
            try:
                resp = await client.get(url)
            except httpx.HTTPError as exc:
                logger.warning("geoip_download_failed", url=url, error=str(exc))
                continue
            if resp.status_code != 200:
                continue
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(gzip.decompress(resp.content))
            tmp.replace(target)
            global _reader
            _reader = None  # reopen on next lookup
            logger.info("geoip_downloaded", month=month, bytes=target.stat().st_size)
            return True
    return False
