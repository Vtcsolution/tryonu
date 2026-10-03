"""An in-memory stand-in for FASHN's API and the CDNs around it.

Used by the direct-engine tests. It is installed by replacing the transport
of every httpx.AsyncClient created while it is active, so NOTHING in these
tests can reach the network: a request to any host the fake doesn't know is
recorded in `unexpected` and answered with a 599, and the tests assert that
list stays empty. No FASHN, OpenAI or Gemini credit can be spent.
"""

from __future__ import annotations

import asyncio
import io
import json

import httpx
from PIL import Image

_real_sleep = asyncio.sleep

FASHN_HOST = "api.fashn.ai"
OUTPUT_HOST = "cdn.fashn.test"
PRODUCT_HOST = "shop.example"


def image_bytes(size: tuple[int, int], color, *, fmt: str = "PNG", rect: tuple[int, int, int, int] | None = None, rect_color=(200, 30, 40)) -> bytes:
    img = Image.new("RGB", size, color)
    if rect:
        img.paste(Image.new("RGB", (rect[2] - rect[0], rect[3] - rect[1]), rect_color), rect[:2])
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class FakeFashn:
    """Scripted FASHN. `statuses` is consumed one poll at a time; the last
    entry repeats. A status may be a string ("processing", "completed",
    "failed"), a ("http", code) pair, or "connect-error"."""

    def __init__(
        self,
        *,
        output: bytes,
        product: bytes | None = None,
        job_id: str = "job_test_1",
        statuses: list | None = None,
        submit_script: list | None = None,
        output_statuses: list[int] | None = None,
        output_content_type: str = "image/png",
        failed_error: object = "boom",
    ) -> None:
        self.output = output
        self.product = product
        self.job_id = job_id
        self.statuses = list(statuses or ["completed"])
        self.submit_script = list(submit_script or [])  # per-attempt: None = accept, int = http status, "read-timeout", "connect-error"
        self.output_statuses = list(output_statuses or [200])
        self.output_content_type = output_content_type
        self.failed_error = failed_error
        self.run_bodies: list[dict] = []
        self.status_paths: list[str] = []
        self.output_fetches = 0
        self.product_fetches = 0
        self.unexpected: list[str] = []

    @property
    def run_count(self) -> int:
        return len(self.run_bodies)

    async def handler(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == FASHN_HOST and path.endswith("/run"):
            self.run_bodies.append(json.loads(request.content))
            action = self.submit_script.pop(0) if self.submit_script else None
            if action == "connect-error":
                raise httpx.ConnectError("no route", request=request)
            if action == "read-timeout":
                raise httpx.ReadTimeout("timed out", request=request)
            if action == "out-of-credits":
                return httpx.Response(429, json={"error": "OutOfCredits"})
            if isinstance(action, int):
                return httpx.Response(action, json={"error": "scripted"})
            return httpx.Response(200, json={"id": self.job_id})
        if host == FASHN_HOST and "/status/" in path:
            self.status_paths.append(path)
            step = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            if step == "connect-error":
                raise httpx.ConnectError("no route", request=request)
            if isinstance(step, tuple):
                return httpx.Response(step[1], text="scripted")
            if step == "completed":
                return httpx.Response(200, json={"status": "completed", "output": [f"https://{OUTPUT_HOST}/result.png"]})
            if step == "failed":
                return httpx.Response(200, json={"status": "failed", "error": self.failed_error})
            return httpx.Response(200, json={"status": step})
        if host == OUTPUT_HOST:
            self.output_fetches += 1
            code = self.output_statuses.pop(0) if len(self.output_statuses) > 1 else self.output_statuses[0]
            if code >= 400:
                return httpx.Response(code, text="gone")
            return httpx.Response(200, content=self.output, headers={"content-type": self.output_content_type})
        if host == PRODUCT_HOST and self.product is not None:
            self.product_fetches += 1
            return httpx.Response(200, content=self.product, headers={"content-type": "image/jpeg"})
        if host == PRODUCT_HOST:
            self.product_fetches += 1
            return httpx.Response(404)
        self.unexpected.append(str(request.url))
        return httpx.Response(599, text="no network in tests")

    def install(self, monkeypatch) -> None:  # noqa: ANN001
        transport = httpx.MockTransport(self.handler)
        original_init = httpx.AsyncClient.__init__

        def patched_init(client, *args, **kwargs):  # noqa: ANN001
            # leave a client that was built with its own transport (the
            # ASGI test client) alone; everything else goes to the fake
            kwargs.setdefault("transport", transport)
            original_init(client, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

        async def fast_sleep(_seconds, *_a, **_kw):  # noqa: ANN001
            await _real_sleep(0)

        monkeypatch.setattr("app.ai.providers.fashn.asyncio.sleep", fast_sleep)
