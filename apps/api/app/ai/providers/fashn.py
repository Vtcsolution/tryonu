"""FASHN.ai virtual try-on provider.

Implements FASHN's documented async run/poll API:
  POST {base}/run     {model_name, inputs{...}} -> {id}
  GET  {base}/status/{id}                       -> {status, output[]}

Both the "tryon-v1.6" and "tryon-max" models share this same run/poll
shape — only the `model` field in the request body differs — so one class
covers both; app.core.config.FASHN_MODEL picks which.

Money rules (every accepted job is billed):
  * A job is submitted at most once. Only failures that happen BEFORE FASHN
    accepted it (could not connect, a 5xx/429 answer) are retried; an
    ambiguous failure (a read timeout after the request was sent) is not,
    because the job may exist.
  * Once a job id exists, nothing ever resubmits. Polling rides out
    transient errors on the SAME id until a generous deadline; if the
    deadline passes, or the download fails, the error carries the job id and
    is not retryable — it can still be fetched from FASHN afterwards.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import httpx

from app.ai.providers.base import TryOnInput, TryOnOutput, TryOnProviderError, VirtualTryOnProvider

_TERMINAL_OK = {"completed"}
_TERMINAL_FAIL = {"failed"}
_POLL_INTERVAL_SECONDS = 2.0
# FASHN documents 20-120s per tryon-max render; the margin covers queueing
_POLL_TIMEOUT_SECONDS = 300.0
_SUBMIT_ATTEMPTS = 3
_DOWNLOAD_ATTEMPTS = 3
_HTTP_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
_CONNECT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_text(error: object) -> str:
    """FASHN reports a failure either as a string or as {name, message}."""
    if isinstance(error, dict):
        return str(error.get("message") or error.get("name") or error)
    return str(error) if error else "FASHN generation failed"


class FASHNTryOnProvider(VirtualTryOnProvider):
    name = "fashn"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        resolution: str = "2k",
        generation_mode: str = "quality",
        output_format: str = "png",
        poll_timeout: float = _POLL_TIMEOUT_SECONDS,
        poll_interval: float = _POLL_INTERVAL_SECONDS,
    ) -> None:
        self.model = model
        self.resolution = resolution
        self.generation_mode = generation_mode
        self.output_format = output_format
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._poll_timeout = poll_timeout
        self._poll_interval = poll_interval

    async def generate(
        self, payload: TryOnInput, *, on_submitted: Callable[[str], Awaitable[None]] | None = None
    ) -> TryOnOutput:
        start = time.perf_counter()
        headers = {"Authorization": f"Bearer {self._api_key}"}
        meta: dict = {
            "model": self.model,
            "resolution": self.resolution if self.model == "tryon-max" else None,
            "generation_mode": self.generation_mode if self.model == "tryon-max" else "quality",
            "output_format": self.output_format if self.model == "tryon-max" else None,
            "prompt": payload.prompt or None,
            "seed": payload.seed,
        }

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            submit_resp = await self._submit_once_accepted(client, headers, payload, meta)
            provider_job_id = submit_resp["id"]
            meta["provider_job_id"] = provider_job_id
            meta["submitted_at"] = _now()
            # FASHN has accepted and may bill this job from here on. Recording
            # its id before polling means a worker that dies mid-poll still
            # leaves a paid render we can look up, instead of an orphan.
            if on_submitted is not None:
                await on_submitted(provider_job_id)

            output_url = await self._poll(client, headers, provider_job_id, meta)
            meta["fashn_completed_at"] = _now()

            image_bytes, content_type = await self._download(client, output_url, provider_job_id)
            meta["downloaded_at"] = _now()

        latency_ms = int((time.perf_counter() - start) * 1000)
        meta["latency_ms"] = latency_ms
        meta["output_bytes"] = len(image_bytes)
        meta["output_sha256"] = hashlib.sha256(image_bytes).hexdigest()
        return TryOnOutput(
            image_bytes=image_bytes,
            content_type=content_type,
            provider_job_id=provider_job_id,
            latency_ms=latency_ms,
            meta=meta,
        )

    def _inputs(self, payload: TryOnInput) -> dict:
        # tryon-v1.6 and tryon-max do NOT share an inputs schema, despite both
        # posting to the same /run endpoint — confirmed directly against
        # FASHN's API (not just docs): tryon-max rejects "garment_image" and
        # "category" outright ("not allowed") and requires "product_image"
        # instead. Sending v1.6's shape to tryon-max 400s on every single
        # request; the account's real-money generation spend was never
        # actually reaching the model.
        if self.model == "tryon-max":
            inputs = {
                "model_image": payload.model_image_url,
                "product_image": payload.garment_image_url,
                "resolution": self.resolution,
                "generation_mode": self.generation_mode,
                "output_format": self.output_format,
                "num_images": 1,
            }
            if payload.prompt:
                inputs["prompt"] = payload.prompt
            if payload.seed is not None:
                inputs["seed"] = payload.seed
            return inputs
        inputs = {
            "model_image": payload.model_image_url,
            "garment_image": payload.garment_image_url,
            "category": payload.category,
            "mode": "quality",
        }
        if payload.seed is not None:
            inputs["seed"] = payload.seed
        return inputs

    async def _submit_once_accepted(
        self, client: httpx.AsyncClient, headers: dict, payload: TryOnInput, meta: dict
    ) -> dict:
        """Submits the job, retrying only what provably never reached FASHN's
        billing: a connection that could not be made, a 5xx, a rate limit.
        Returns as soon as FASHN accepts a job — never submits a second."""
        for attempt in range(1, _SUBMIT_ATTEMPTS + 1):
            meta["submit_attempts"] = attempt
            try:
                return await self._submit(client, headers, payload)
            except TryOnProviderError as exc:
                if not exc.retryable or attempt == _SUBMIT_ATTEMPTS:
                    raise
                await asyncio.sleep(min(2.0 * 2**attempt, 30.0))
        raise AssertionError("unreachable")  # pragma: no cover

    async def _submit(self, client: httpx.AsyncClient, headers: dict, payload: TryOnInput) -> dict:
        try:
            resp = await client.post(
                f"{self._base_url}/run",
                headers=headers,
                json={"model_name": self.model, "inputs": self._inputs(payload)},
            )
        except _CONNECT_ERRORS as exc:
            # never connected, so nothing was submitted: safe to try again
            raise TryOnProviderError(f"FASHN request failed: {exc}", retryable=True) from exc
        except httpx.RequestError as exc:
            # the request may have been delivered before this failed — the job
            # might exist and be billed. Not resubmitting is the safe answer.
            raise TryOnProviderError(
                f"FASHN request failed after it was sent ({type(exc).__name__}); not resubmitting, "
                "because the job may already exist and be billed",
            ) from exc

        if resp.status_code >= 500:
            raise TryOnProviderError(f"FASHN server error {resp.status_code}", retryable=True)
        if resp.status_code == 429:
            # FASHN answers 429 for an empty balance too — that one won't
            # fix itself, and "rate limited" hid it from the admin
            if "OutOfCredits" in resp.text:
                raise TryOnProviderError(
                    "The FASHN account is out of credits — top up at app.fashn.ai to resume try-ons"
                )
            raise TryOnProviderError("FASHN rate limited", retryable=True)
        if resp.status_code >= 400:
            raise TryOnProviderError(f"FASHN rejected request: {resp.status_code} {resp.text}")

        data = resp.json()
        if not isinstance(data, dict) or not data.get("id"):
            raise TryOnProviderError(f"FASHN accepted the request but returned no job id: {str(data)[:200]}")
        return data

    async def _poll(self, client: httpx.AsyncClient, headers: dict, job_id: str, meta: dict) -> str:
        """Polls ONE job until it finishes. Transient trouble (a dropped
        connection, a 5xx, a 429) just means asking again — the job is
        running on FASHN's side regardless of whether we can see it."""
        deadline = time.monotonic() + self._poll_timeout
        polls = transient = 0
        while True:
            if time.monotonic() >= deadline:
                meta["poll_count"], meta["poll_transient_errors"] = polls, transient
                raise TryOnProviderError(
                    f"FASHN job {job_id} was still not finished after {int(self._poll_timeout)}s. "
                    "It was NOT resubmitted (that would be billed again); it may still complete on FASHN's side.",
                    provider_job_id=job_id,
                )
            polls += 1
            try:
                resp = await client.get(f"{self._base_url}/status/{job_id}", headers=headers)
            except httpx.RequestError:
                transient += 1
            else:
                if resp.status_code == 429 or resp.status_code >= 500:
                    transient += 1
                elif resp.status_code >= 400:
                    meta["poll_count"], meta["poll_transient_errors"] = polls, transient
                    raise TryOnProviderError(
                        f"FASHN poll error {resp.status_code}: {resp.text}", provider_job_id=job_id
                    )
                else:
                    data = resp.json()
                    status_ = data.get("status")
                    if status_ in _TERMINAL_OK:
                        outputs = data.get("output") or []
                        meta["poll_count"], meta["poll_transient_errors"] = polls, transient
                        if not outputs:
                            raise TryOnProviderError(
                                "FASHN completed with no output image", provider_job_id=job_id
                            )
                        return outputs[0]
                    if status_ in _TERMINAL_FAIL:
                        meta["poll_count"], meta["poll_transient_errors"] = polls, transient
                        raise TryOnProviderError(_error_text(data.get("error")), provider_job_id=job_id)

            await asyncio.sleep(self._poll_interval)

    async def _download(self, client: httpx.AsyncClient, url: str, job_id: str) -> tuple[bytes, str]:
        """Fetches the finished image. Fetching is repeatable and free, so
        this retries — but a failure here is still never retryable at the job
        level: the render exists and is paid for."""
        last = "unknown error"
        for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
            try:
                resp = await client.get(url)
            except httpx.RequestError as exc:
                last = str(exc) or type(exc).__name__
            else:
                if resp.status_code < 400:
                    return resp.content, self._content_type(resp)
                last = str(resp.status_code)
            if attempt < _DOWNLOAD_ATTEMPTS:
                await asyncio.sleep(1.0 * attempt)
        raise TryOnProviderError(
            f"Failed to download the finished FASHN render for job {job_id}: {last}", provider_job_id=job_id
        )

    def _content_type(self, resp: httpx.Response) -> str:
        header = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if header.startswith("image/"):
            return header
        return "image/png" if self.output_format == "png" else "image/jpeg"
