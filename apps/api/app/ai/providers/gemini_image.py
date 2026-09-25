"""Google Gemini image editing ("nano banana") as a try-on engine.

The same shape of call as the OpenAI adapter beside it: the person's
photo and every product photo go into one request, with a prompt that
says what each product is and how it is worn. The prompt is literally
the same one — see openai_image.build_prompt — so a comparison between
the two engines is a comparison of the engines, not of two prompts.

Why it is worth having: our whole compositing apparatus exists because
the engine we use does not reliably give the person back unchanged. It
returns a new photograph, so we find what changed, decide which of those
changes are the product, and paste only those onto the customer's own
pixels. Every artifact a customer has ever complained about — a seam
across the collarbone, hair replaced by background, a blouse spattered
across a wedding hall — comes from that step, not from the drawing. An
engine that preserves the face, the body and the room faithfully enough
to be used whole would delete the entire class.

That is a claim to measure, not to believe. This adapter exists so it
can be measured against the same photos, the same products and the same
inspector.
"""

from __future__ import annotations

import base64
import time

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.ai.providers.base import OutfitPiece, TryOnInput, TryOnOutput, TryOnProviderError, VirtualTryOnProvider
from app.ai.providers.openai_image import MAX_PIECES, _download, _slot_from_category, build_prompt
from app.core.logging import logger

_TIMEOUT_SECONDS = 300.0

# Gemini takes an aspect ratio rather than a pixel size, and matching the
# photo's own keeps the edit an edit instead of a re-framing.
_RATIOS = {"portrait": "3:4", "landscape": "4:3", "square": "1:1"}

# Models that answered 400 to an image config. Asked once per process:
# the answer cannot change under us, and asking again costs a full
# re-upload of the photo and every product image.
_NO_IMAGE_CONFIG: set[str] = set()


# Said before anything else, and in these words, because without it this
# engine treats the *product* photo as the picture to edit. Measured on
# the same look: with the shared prompt alone, 98% of the customer's face
# and hair came back different — it had returned a photograph of the
# model from the eBay listing, standing in her garden. With this, 37%,
# and the woman in the result is the customer, in her own room.
_CANVAS = (
    "This is a virtual try-on for an online shop.\n\n"
    "THE FIRST IMAGE IS THE CUSTOMER. The output must be that same woman, in that same room, in that "
    "same pose, with only her clothes and accessories changed. Her face, her hair, her skin, her body, "
    "the wall behind her and the floor she stands on come out as they went in.\n\n"
    "THE IMAGES AFTER IT ARE SHOP CATALOGUE PHOTOS. Some show a different model wearing the item, "
    "somewhere else entirely. Ignore that model and ignore that place completely — take only the garment "
    "or the object itself. Never return a picture of the catalogue's model, and never return a picture "
    "taken anywhere but the customer's own room."
)


def _aspect_ratio(photo: bytes) -> str:
    try:
        import cv2
        import numpy as np

        image = cv2.imdecode(np.frombuffer(photo, np.uint8), cv2.IMREAD_COLOR)
        height, width = image.shape[:2]
    except Exception:  # noqa: BLE001 — an unreadable photo is the caller's problem
        return _RATIOS["portrait"]
    ratio = width / height
    if ratio > 1.15:
        return _RATIOS["landscape"]
    if ratio < 0.87:
        return _RATIOS["portrait"]
    return _RATIOS["square"]


# Asked for explicitly, because the default is small. Measured on the
# same edit, with every result brought down to a common size so the
# numbers compare:
#   default  896x1200   detail 428
#   2K      1792x2400   detail 453   — four times the pixels, and real
#   4K      3584x4800   detail 259   — sixteen times the pixels, and soft
# 4K is an enlargement of the same drawing, so it is worse at any size
# you would actually look at it.
DEFAULT_IMAGE_SIZE = "2K"


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, TryOnProviderError) and exc.retryable


class GeminiImageTryOnProvider(VirtualTryOnProvider):
    name = "gemini"
    whole_outfit = True
    # Measured on the same photo and products, as the share of the
    # customer's face and hair that came back different from her own
    # photo: 27% here against 38% for the engine we were using — and the
    # Gemini figure is the raw render, where ours is after all the
    # compositing. It keeps her room, her pose and her own shoes.
    preserves_person = True

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        image_size: str = "2K",
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._image_size = image_size

    def at_quality(self, quality: str) -> "GeminiImageTryOnProvider":  # noqa: ARG002
        """Gemini has no quality dial — the same engine answers both the
        everyday render and the detailed retry. Kept so the quality
        pipeline can ask without knowing which engine it is talking to."""
        return self

    async def generate(self, payload: TryOnInput) -> TryOnOutput:
        piece = OutfitPiece(
            image_url=payload.garment_image_url,
            slot=_slot_from_category(payload.category),
            name="the product",
        )
        return await self.generate_outfit(payload.model_image_url, [piece])

    @retry(
        retry=retry_if_exception(_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=16),
        reraise=True,
    )
    async def generate_outfit(self, model_image_url: str, pieces: list[OutfitPiece]) -> TryOnOutput:
        if not pieces:
            raise TryOnProviderError("Nothing to try on")
        pieces = pieces[:MAX_PIECES]
        start = time.perf_counter()

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=True) as client:
            person = await _download(client, model_image_url, "your photo")
            products = [await _download(client, p.image_url, p.name) for p in pieces]
            # Each image is announced by the text part before it. The
            # prompt numbers them — "Image 1 is a photo of a real person",
            # "Image 2 is one product photo" — and nothing else tells this
            # API which attachment is which. Unlabelled, it took the
            # product listing's own model and her garden as the base and
            # returned a photograph of a stranger.
            parts: list[dict] = [{"text": _CANVAS + "\n\n" + build_prompt(pieces)}]
            labelled = [("Image 1 — the real person, to be kept exactly:", person)]
            labelled += [
                (f"Image {n} — product photo of: {piece.name[:120]}", product)
                for n, (piece, product) in enumerate(zip(pieces, products), start=2)
            ]
            for label, (content, ctype) in labelled:
                parts.append({"text": label})
                parts.append(
                    {"inlineData": {"mimeType": ctype, "data": base64.b64encode(content).decode()}}
                )
            body = {
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"responseModalities": ["IMAGE"]},
            }
            if self.model not in _NO_IMAGE_CONFIG:
                config = {"aspectRatio": _aspect_ratio(person[0])}
                if self._image_size:
                    config["imageSize"] = self._image_size
                body["generationConfig"]["imageConfig"] = config
            resp = await self._post(client, body)
            if resp.status_code == 400 and "imageConfig" in resp.text:
                logger.info("gemini_image_no_image_config", model=self.model)
                _NO_IMAGE_CONFIG.add(self.model)
                body["generationConfig"].pop("imageConfig", None)
                resp = await self._post(client, body)

        _raise_for_status(resp)
        image, ctype = _first_image(resp.json())
        return TryOnOutput(
            image_bytes=image,
            content_type=ctype,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    async def _post(self, client: httpx.AsyncClient, body: dict) -> httpx.Response:
        try:
            return await client.post(
                f"{self._base_url}/models/{self.model}:generateContent",
                headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
                json=body,
            )
        except httpx.RequestError as exc:
            raise TryOnProviderError(f"Gemini request failed: {exc}", retryable=True) from exc


def _first_image(payload: dict) -> tuple[bytes, str]:
    """The image out of a response that also carries text and metadata.

    A refusal comes back as a perfectly successful response with no image
    part in it, so the absence of one is reported with whatever the model
    said instead — that is the difference between "it wouldn't" and "it
    broke"."""
    said: list[str] = []
    for candidate in payload.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                ctype = blob.get("mimeType") or blob.get("mime_type") or "image/png"
                return base64.b64decode(blob["data"]), ctype
            if part.get("text"):
                said.append(part["text"])
    reason = "; ".join(said)[:200] or "no image in the response"
    raise TryOnProviderError(f"Gemini returned no image: {reason}")


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    try:
        message = resp.json()["error"]["message"]
    except Exception:  # noqa: BLE001 — a non-JSON error is still an error
        message = resp.text[:300]
    # 429 and 5xx are worth another go; a bad request never is
    retryable = resp.status_code == 429 or resp.status_code >= 500
    raise TryOnProviderError(f"Gemini {resp.status_code}: {message}", retryable=retryable)
