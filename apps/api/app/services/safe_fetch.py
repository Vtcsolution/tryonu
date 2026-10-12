"""Fetching web addresses that companies give us, safely.

A company's feed link and product photo links are fetched by OUR server. A
malicious link could point at our own network instead (http://127.0.0.1:6379,
the cloud metadata address 169.254.169.254, ...) to probe it: server-side
request forgery. Every such link must be http(s) to a host that resolves only
to public addresses, every redirect is checked the same way, and downloads
stop at a size limit.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx


class UnsafeURLError(ValueError):
    """The link isn't a public web address we may fetch."""


def check_public_url(url: str) -> str:
    """The link itself, if it is http(s) to a public host; raises UnsafeURLError otherwise."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURLError("must be an http(s) web address")
    if parsed.username or parsed.password:
        raise UnsafeURLError("must not contain a username or password")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeURLError("host not found") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise UnsafeURLError("must point to a public internet address")
    return url.strip()


def _guard(request: httpx.Request) -> None:
    check_public_url(str(request.url))


def fetch_limited(url: str, *, max_bytes: int, timeout: float = 60.0) -> bytes:
    """The body of a public URL, at most max_bytes; every redirect re-checked."""
    check_public_url(url)
    with httpx.Client(
        follow_redirects=True,
        max_redirects=5,
        timeout=timeout,
        event_hooks={"request": [_guard]},
        headers={"User-Agent": "TryOnU-Store-Import/1.0"},
    ) as client:
        with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            data = bytearray()
            for chunk in resp.iter_bytes():
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise RuntimeError(f"larger than {max_bytes // (1024 * 1024)} MB")
            return bytes(data)
