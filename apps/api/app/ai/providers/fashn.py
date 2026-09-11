"""FASHN.ai virtual try-on provider.

Implements FASHN's documented async run/poll API:
  POST {base}/run     {model_image, garment_image, category} -> {id}
  GET  {base}/status/{id}                                    -> {status, output[]}

Both the "tryon-v1.6" and "tryon-max" models share this same run/poll
shape — only the `model` field in the request body differs — so one class
covers both; app.core.config.FASHN_MODEL picks which.
"""

from __future__ import annotations

import asyncio
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.providers.base import TryOnInput, TryOnOutput, TryOnProviderError, VirtualTryOnProvider

_TERMINAL_OK = {"completed"}
_TERMINAL_FAIL = {"failed"}
_POLL_INTERVAL_SECONDS = 2.0
_POLL_TIMEOUT_SECONDS = 90.0


class FASHNTryOnProvider(VirtualTryOnProvider):
    name = "fashn"

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @retry(
        retry=retry_if_exception_type(TryOnProviderError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def generate(self, payload: TryOnInput) -> TryOnOutput:
        start = time.perf_counter()
        headers = {"Authorization": f"Bearer {self._api_key}"}

        async with httpx.AsyncClient(timeout=30) as client:
            submit_resp = await self._submit(client, headers, payload)
            provider_job_id = submit_resp["id"]
            output_url = await self._poll(client, headers, provider_job_id)
            image_bytes = await self._download(client, output_url)

        latency_ms = int((time.perf_counter() - start) * 1000)
        return TryOnOutput(
            image_bytes=image_bytes,
            provider_job_id=provider_job_id,
            latency_ms=latency_ms,
        )

    async def _submit(self, client: httpx.AsyncClient, headers: dict, payload: TryOnInput) -> dict:
        try:
            resp = await client.post(
                f"{self._base_url}/run",
                headers=headers,
                json={
                    "model_name": self.model,
                    "inputs": {
                        "model_image": payload.model_image_url,
                        "garment_image": payload.garment_image_url,
                        "category": payload.category,
                    },
                },
            )
        except httpx.RequestError as exc:
            raise TryOnProviderError(f"FASHN request failed: {exc}", retryable=True) from exc

        if resp.status_code >= 500:
            raise TryOnProviderError(f"FASHN server error {resp.status_code}", retryable=True)
        if resp.status_code == 429:
            raise TryOnProviderError("FASHN rate limited", retryable=True)
        if resp.status_code >= 400:
            raise TryOnProviderError(f"FASHN rejected request: {resp.status_code} {resp.text}")

        return resp.json()

    async def _poll(self, client: httpx.AsyncClient, headers: dict, job_id: str) -> str:
        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                resp = await client.get(f"{self._base_url}/status/{job_id}", headers=headers)
            except httpx.RequestError as exc:
                raise TryOnProviderError(f"FASHN poll failed: {exc}", retryable=True) from exc

            if resp.status_code >= 400:
                raise TryOnProviderError(f"FASHN poll error {resp.status_code}: {resp.text}")

            data = resp.json()
            status_ = data.get("status")
            if status_ in _TERMINAL_OK:
                outputs = data.get("output") or []
                if not outputs:
                    raise TryOnProviderError("FASHN completed with no output image")
                return outputs[0]
            if status_ in _TERMINAL_FAIL:
                raise TryOnProviderError(data.get("error", "FASHN generation failed"))

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

        raise TryOnProviderError("FASHN generation timed out", retryable=True)

    async def _download(self, client: httpx.AsyncClient, url: str) -> bytes:
        try:
            resp = await client.get(url)
        except httpx.RequestError as exc:
            raise TryOnProviderError(f"Failed to download FASHN result: {exc}", retryable=True) from exc
        if resp.status_code >= 400:
            raise TryOnProviderError(f"Failed to download FASHN result: {resp.status_code}")
        return resp.content
