"""Text embeddings for product search + the stylist's nearest-neighbour
matching.

Real path: OpenAI's /embeddings endpoint when OPENAI_API_KEY is set.
Fallback: a deterministic hashing-trick "embedding" (no external call) so
ingestion and cosine-similarity search are fully exercisable offline — it
won't produce semantically meaningful neighbours, but every code path
(store vector -> query vector -> rank by cosine) runs for real.
"""

from __future__ import annotations

import hashlib
import math

import httpx

from app.core.config import get_settings

settings = get_settings()


async def embed_text(text: str) -> list[float]:
    if settings.OPENAI_API_KEY:
        return await _embed_openai(text)
    return _embed_hash(text)


async def _embed_openai(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={"model": settings.OPENAI_EMBEDDING_MODEL, "input": text},
        )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def _embed_hash(text: str, dim: int | None = None) -> list[float]:
    dim = dim or settings.EMBEDDING_DIM
    vec = [0.0] * dim
    for token in text.lower().split():
        h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def product_embedding_text(*, name: str, brand: str | None, category: str | None, color: str | None, description: str | None, style_tags: list[str] | None) -> str:
    parts = [name, brand or "", category or "", color or "", description or "", " ".join(style_tags or [])]
    return " ".join(p for p in parts if p)
