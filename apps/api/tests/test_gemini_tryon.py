"""Gemini image editing as a try-on engine: the person's photo and every
product photo go into one generateContent call, with the same prompt the
OpenAI adapter uses, so a comparison between the two is a comparison of
the engines. No real network calls."""

from __future__ import annotations

import base64

import httpx
import pytest

from app.ai.providers.base import OutfitPiece, TryOnProviderError
from app.ai.providers.gemini_image import GeminiImageTryOnProvider
from tests.conftest import small_jpeg_bytes

RESULT = b"\xff\xd8rendered-look"


def _provider() -> GeminiImageTryOnProvider:
    return GeminiImageTryOnProvider(api_key="test-key", model="gemini-2.5-flash-image")


def _answer(parts: list[dict], status: int = 200) -> httpx.Response:
    if status >= 400:
        return httpx.Response(status, json={"error": {"message": "nope"}})
    return httpx.Response(status, json={"candidates": [{"content": {"parts": parts}}]})


def _image_part(data: bytes = RESULT, mime: str = "image/png") -> dict:
    return {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}


@pytest.fixture
def transport(monkeypatch):
    """Answers the photo/product downloads and records the edit request."""
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host != "generativelanguage.googleapis.com":
            return httpx.Response(200, content=small_jpeg_bytes(), headers={"content-type": "image/jpeg"})
        sent.append({"headers": dict(request.headers), "json": __import__("json").loads(request.content)})
        return _answer([_image_part()])

    real = httpx.AsyncClient

    class Recording(real):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    monkeypatch.setattr(httpx, "AsyncClient", Recording)
    return sent


async def test_the_person_and_every_product_go_in_one_call(transport):
    out = await _provider().generate_outfit(
        "https://img/person.jpg",
        [
            OutfitPiece("https://img/kameez.jpg", "dress", "Pakistani Lawn Suit"),
            OutfitPiece("https://img/tote.jpg", "bag", "Leather Tote"),
        ],
    )

    assert out.image_bytes == RESULT
    assert len(transport) == 1
    body = transport[0]["json"]
    parts = body["contents"][0]["parts"]
    # the customer is named as the canvas before anything else: without
    # it this engine edits the product photo and returns a stranger
    assert parts[0]["text"].startswith("This is a virtual try-on")
    assert "THE FIRST IMAGE IS THE CUSTOMER" in parts[0]["text"]
    assert "Image 1 is a photo of a real person" in parts[0]["text"]  # ...then the shared prompt
    assert sum(1 for p in parts if "inlineData" in p) == 3  # the person and both products
    # and every image is announced, because nothing else says which is which
    labels = [p["text"] for p in parts[1:] if "text" in p]
    assert labels[0].startswith("Image 1 — the real person")
    assert "Pakistani Lawn Suit" in labels[1] and "Leather Tote" in labels[2]
    assert body["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert transport[0]["headers"]["x-goog-api-key"] == "test-key"


async def test_the_products_keep_their_preservation_rules(transport):
    """The prompt is the OpenAI adapter's, so what a shopper would notice
    was wrong about a bag reaches this engine too."""
    await _provider().generate_outfit(
        "https://img/person.jpg", [OutfitPiece("https://img/b.jpg", "bag", "Tote with Embossed Base")]
    )
    prompt = transport[0]["json"]["contents"][0]["parts"][0]["text"]
    assert "handles" in prompt and "embossed" in prompt


async def test_a_refusal_is_reported_as_a_refusal_not_a_crash(monkeypatch):
    """A refusal comes back as a perfectly successful response with no
    image in it — the difference between "it wouldn't" and "it broke"."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host != "generativelanguage.googleapis.com":
            return httpx.Response(200, content=small_jpeg_bytes(), headers={"content-type": "image/jpeg"})
        return _answer([{"text": "I can't edit photographs of real people."}])

    real = httpx.AsyncClient

    class Refusing(real):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    monkeypatch.setattr(httpx, "AsyncClient", Refusing)

    with pytest.raises(TryOnProviderError) as raised:
        await _provider().generate_outfit("https://img/p.jpg", [OutfitPiece("https://img/g.jpg", "top", "Shirt")])
    assert "can't edit photographs" in str(raised.value)


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(429, True), (500, True), (400, False)],
)
async def test_only_worth_retrying_is_retried(monkeypatch, status, retryable):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host != "generativelanguage.googleapis.com":
            return httpx.Response(200, content=small_jpeg_bytes(), headers={"content-type": "image/jpeg"})
        return _answer([], status=status)

    real = httpx.AsyncClient

    class Failing(real):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    monkeypatch.setattr(httpx, "AsyncClient", Failing)

    with pytest.raises(TryOnProviderError) as raised:
        await _provider().generate_outfit("https://img/p.jpg", [OutfitPiece("https://img/g.jpg", "top", "Shirt")])
    assert raised.value.retryable is retryable


async def test_an_unconfigured_key_never_selects_this_engine(monkeypatch):
    """A half-configured deploy renders with the mock rather than failing
    every job at the provider."""
    from app.core.config import Settings

    settings = Settings(VIRTUAL_TRYON_PROVIDER="gemini", GEMINI_API_KEY=None)
    assert settings.VIRTUAL_TRYON_PROVIDER == "mock"
