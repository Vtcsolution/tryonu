"""Mock virtual try-on provider — used automatically whenever no FASHN_API_KEY
is configured (see app/core/config.py). Lets the entire job pipeline
(queueing, credit debit/refund, status polling, storage) run and be tested
end-to-end with zero external credentials. It still respects the contract:
given a real product image URL, it must return *that* image (never an
unrelated one) — here, downloaded and lightly stamped so it's obviously a
mock, not passed off as a real AI render.
"""

from __future__ import annotations

import asyncio
import io
import random
import time

import httpx
from PIL import Image, ImageDraw

from app.ai.providers.base import TryOnInput, TryOnOutput, TryOnProviderError, VirtualTryOnProvider


class MockTryOnProvider(VirtualTryOnProvider):
    name = "mock"
    model = "mock-v1"

    async def generate(self, payload: TryOnInput) -> TryOnOutput:
        start = time.perf_counter()
        await asyncio.sleep(random.uniform(1.5, 3.0))  # simulate a real render's latency

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(payload.garment_image_url)
                resp.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise TryOnProviderError(f"mock provider could not fetch garment image: {exc}", retryable=True) from exc

        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")
        h = img.height
        draw.rectangle([0, h - 44, img.width, h], fill=(30, 33, 28, 190))
        draw.text((16, h - 32), "TryOnU · mock AI render (no FASHN_API_KEY set)", fill=(255, 255, 255, 255))

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=90)

        return TryOnOutput(
            image_bytes=out.getvalue(),
            provider_job_id=f"mock_{random.randint(100000, 999999)}",
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
