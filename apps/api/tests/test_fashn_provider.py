"""Locks in the real FASHN request shape (discovered by testing against
the live API — the initial flat-field guess was rejected with a 400).
No real FASHN credits are spent: httpx is monkeypatched to a fake
transport that asserts on the outgoing request and returns canned
responses."""

from __future__ import annotations

import httpx
import pytest

from app.ai.providers.base import TryOnInput, TryOnProviderError
from app.ai.providers.fashn import FASHNTryOnProvider


def _fake_transport(*, submit_payload_check, poll_status: str = "completed"):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/run"):
            body = httpx.Request("POST", request.url, content=request.content).content
            import json

            data = json.loads(body)
            submit_payload_check(data)
            return httpx.Response(200, json={"id": "job_abc123"})
        if "/status/" in request.url.path:
            return httpx.Response(
                200,
                json={"status": poll_status, "output": ["https://cdn.example/result.jpg"]},
            )
        if request.url.host == "cdn.example":
            return httpx.Response(200, content=b"fake-image-bytes", headers={"content-type": "image/jpeg"})
        raise AssertionError(f"unexpected request: {request.url}")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fashn_submit_uses_model_name_and_inputs_shape(monkeypatch):
    """Regression test for the real bug: FASHN rejects flat top-level
    model_image/garment_image fields and requires {"model_name", "inputs": {...}}."""
    captured = {}

    def check(data):
        captured.update(data)

    transport = _fake_transport(submit_payload_check=check)

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
    # avoid a real 2s sleep in the poll loop
    monkeypatch.setattr("app.ai.providers.fashn.asyncio.sleep", lambda *_a, **_kw: _noop())

    provider = FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model="tryon-v1.6")
    output = await provider.generate(
        TryOnInput(model_image_url="https://example.com/model.jpg", garment_image_url="https://example.com/garment.jpg")
    )

    assert captured["model_name"] == "tryon-v1.6"
    assert captured["inputs"]["model_image"] == "https://example.com/model.jpg"
    assert captured["inputs"]["garment_image"] == "https://example.com/garment.jpg"
    assert "model_image" not in captured  # must be nested, not top-level
    assert output.image_bytes == b"fake-image-bytes"
    assert output.provider_job_id == "job_abc123"


@pytest.mark.asyncio
async def test_fashn_failed_status_raises_provider_error(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/run"):
            return httpx.Response(200, json={"id": "job_fail"})
        return httpx.Response(200, json={"status": "failed", "error": "face not detected"})

    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    provider = FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model="tryon-v1.6")
    with pytest.raises(TryOnProviderError, match="face not detected"):
        await provider.generate(
            TryOnInput(model_image_url="https://example.com/model.jpg", garment_image_url="https://example.com/garment.jpg")
        )


async def _noop(*_a, **_kw):
    return None
