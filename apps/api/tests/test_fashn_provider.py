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
async def test_fashn_max_submit_uses_product_image_not_garment_image(monkeypatch):
    """Regression test for a real bug found by probing the live FASHN API
    directly: tryon-max rejects "garment_image"/"category" outright
    ("not allowed") and requires "product_image" instead — tryon-v1.6's
    shape does not carry over. Confirmed live: every tryon-max request was
    400ing before this fix, so no generation was ever actually happening
    while that model was configured."""
    captured = {}

    def check(data):
        captured.update(data)

    transport = _fake_transport(submit_payload_check=check)

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
    monkeypatch.setattr("app.ai.providers.fashn.asyncio.sleep", lambda *_a, **_kw: _noop())

    provider = FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model="tryon-max")
    await provider.generate(
        TryOnInput(model_image_url="https://example.com/model.jpg", garment_image_url="https://example.com/garment.jpg")
    )

    assert captured["model_name"] == "tryon-max"
    assert captured["inputs"]["model_image"] == "https://example.com/model.jpg"
    assert captured["inputs"]["product_image"] == "https://example.com/garment.jpg"
    assert "garment_image" not in captured["inputs"]
    assert "category" not in captured["inputs"]


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["tryon-max", "tryon-v1.6"])
async def test_fashn_sends_layer_instructions_in_each_models_own_fields(monkeypatch, model):
    """tryon-max gets the free-text prompt (a documented input); v1.6 has no
    prompt field and gets its explicit category + quality mode instead."""
    captured = {}
    transport = _fake_transport(submit_payload_check=captured.update)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
    monkeypatch.setattr("app.ai.providers.fashn.asyncio.sleep", lambda *_a, **_kw: _noop())

    provider = FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model=model)
    await provider.generate(
        TryOnInput(
            model_image_url="https://example.com/model.jpg",
            garment_image_url="https://example.com/vest.jpg",
            category="tops",
            prompt="Layer this item over the outfit",
        )
    )
    inputs = captured["inputs"]
    if model == "tryon-max":
        assert inputs["prompt"] == "Layer this item over the outfit"
        assert "category" not in inputs
    else:
        assert inputs["category"] == "tops"
        assert inputs["mode"] == "quality"
        assert "prompt" not in inputs


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


@pytest.mark.asyncio
async def test_out_of_credits_is_reported_as_such_and_not_retried(monkeypatch):
    """Real incident: FASHN answers 429 {"error":"OutOfCredits"} for an empty
    balance. It was reported as "rate limited" and retried — every try-on
    on the site failed with a misleading message."""
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            429, json={"error": "OutOfCredits", "message": "You are out of credits. Please visit your account."}
        )

    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
    provider = FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model="tryon-max")
    with pytest.raises(TryOnProviderError) as exc:
        await provider.generate(TryOnInput(model_image_url="https://e.x/m.jpg", garment_image_url="https://e.x/g.jpg"))
    assert "out of credits" in str(exc.value)
    assert not exc.value.retryable
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["tryon-max", "tryon-v1.6"])
async def test_a_seed_is_sent_so_a_retry_is_a_different_render(monkeypatch, model):
    captured = {}
    transport = _fake_transport(submit_payload_check=captured.update)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
    monkeypatch.setattr("app.ai.providers.fashn.asyncio.sleep", lambda *_a, **_kw: _noop())
    provider = FASHNTryOnProvider(api_key="fa-test", base_url="https://api.fashn.ai/v1", model=model)
    await provider.generate(
        TryOnInput(model_image_url="https://e.x/m.jpg", garment_image_url="https://e.x/g.jpg", seed=8003)
    )
    assert captured["inputs"]["seed"] == 8003
