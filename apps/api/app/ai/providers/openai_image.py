"""OpenAI image-editing try-on — the same kind of model ChatGPT uses when
asked to "put these clothes on me".

Unlike FASHN (one garment per call, clothing only on tryon-v1.6), this
sends the person's photo AND every product photo in a single request to
POST {base}/images/edits and asks for the person wearing all of it —
full outfits, layers, shoes, bags and jewellery in one render.

The model is only ever shown the real product photos from the outfit and
told to reproduce those exact items; it's not asked to invent clothing.
"""

from __future__ import annotations

import base64
import time

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.logging import logger
from app.ai.providers.base import OutfitPiece, TryOnInput, TryOnOutput, TryOnProviderError, VirtualTryOnProvider

_TIMEOUT_SECONDS = 300.0  # high-quality edits with several reference images take a while
MAX_PIECES = 15  # the endpoint takes up to 16 images; one is the person

# how each kind of item is worn — keeps a bag in the hand, not on the body
_HOW = {
    "dress": "the complete outfit shown (replaces the person's current top AND trousers)",
    "top": "worn as the top (replaces the current shirt)",
    "bottom": "worn as the trousers/bottom (replaces the current ones)",
    "outerwear": "layered over the outfit (the clothes underneath stay visible where they naturally would)",
    "shoes": "on the feet (replaces the current footwear)",
    "bag": "carried naturally, in the hand or over the shoulder",
    "watch": "worn on the wrist",
    "accessory": "worn where it naturally goes (bangles on the wrists, earrings on the ears, necklace on the neck)",
    "other": "worn or carried where it naturally goes",
}


def build_prompt(pieces: list[OutfitPiece]) -> str:
    lines = [
        "Image 1 is a photo of a real person — possibly a close-up of part of the body, such as a wrist. "
        "Edit it so the same person is wearing the products below.",
        "",
        "Products (each later image is one product photo):",
    ]
    for n, piece in enumerate(pieces, start=2):
        lines.append(f"- Image {n}: {piece.name} — {_HOW.get(piece.slot, 'worn where it naturally goes')}.")
        if piece.description:
            # spelling the product out in words as well as showing it holds
            # the details the image alone kept losing: an ivory dress came
            # back pink, its gold embroidery faint and sparse
            lines.append(f"  It is: {piece.description}")
        if piece.note:
            lines.append(f"  Correction from the previous attempt: {piece.note}")
    lines += [
        "",
        "Rules:",
        "- Keep the person exactly the same: face, identity, skin tone, hair, beard, body shape, pose and expression.",
        "- Keep the background, camera angle, framing and lighting of image 1 unchanged.",
        "- Reproduce each product faithfully: same colour, fabric, pattern, embroidery and cut as in its photo.",
        "- Colour is not approximate: yellow gold is not silver, ivory is not pink, navy is not black. Match the"
        " product photo's exact shade, and keep the metal tone of jewellery and watches (yellow gold, rose gold,"
        " white gold/silver/steel) exactly as shown.",
        "- Fit every item naturally to the person's body and pose, with realistic folds, drape and shadows.",
        "- Take ONLY the product from each product photo: ignore any model, mannequin, hanger, background,"
        " text, logo overlay or watermark in it.",
        "- Replace the clothing the products replace; leave everything else as it is.",
        "- The result must be a single realistic photograph, not a collage.",
    ]
    return "\n".join(lines)


# Models that answered 400 to input_fidelity. Asked once per process, not
# once per render: the answer cannot change under us, and the cost of
# asking is a full re-upload of every image in the request.
_NO_INPUT_FIDELITY: set[str] = set()


# The largest each shape the API will return. Measured against the live
# API: a portrait render at 1536x2048 comes back three times as sharp as
# the 1024x1536 "auto" default, and 2048x3072 measured *worse* — the
# model draws at this scale and anything beyond is its own enlargement.
_SIZES = {"portrait": "1536x2048", "landscape": "2048x1536", "square": "2048x2048"}


def _best_size(photo: bytes) -> str:
    """The biggest render that matches the shape of the photo it edits.

    Asking for a portrait render of a landscape photo would have the model
    re-frame the person; matching the shape keeps the edit an edit."""
    try:
        import cv2
        import numpy as np

        image = cv2.imdecode(np.frombuffer(photo, np.uint8), cv2.IMREAD_COLOR)
        height, width = image.shape[:2]
    except Exception:  # noqa: BLE001 — an unreadable photo is the caller's problem
        return "auto"
    ratio = width / height
    if ratio > 1.15:
        return _SIZES["landscape"]
    if ratio < 0.87:
        return _SIZES["portrait"]
    return _SIZES["square"]


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, TryOnProviderError) and exc.retryable


class OpenAIImageTryOnProvider(VirtualTryOnProvider):
    name = "openai"
    whole_outfit = True

    def __init__(
        self, *, api_key: str, model: str, base_url: str = "https://api.openai.com/v1", quality: str = "high"
    ) -> None:
        self.model = model
        self.quality = quality
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def at_quality(self, quality: str) -> "OpenAIImageTryOnProvider":
        """The same provider rendering at a different quality. Everyday
        renders use the fast setting; the quality pipeline escalates to this
        for an item whose first attempt failed inspection, where the extra
        seconds buy back colour accuracy and fine detail."""
        if quality == self.quality:
            return self
        return OpenAIImageTryOnProvider(
            api_key=self._api_key, model=self.model, base_url=self._base_url, quality=quality
        )

    async def generate(self, payload: TryOnInput) -> TryOnOutput:
        # a single product is a one-item outfit
        piece = OutfitPiece(
            image_url=payload.garment_image_url, slot=_slot_from_category(payload.category), name="the product"
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
            files = [("image[]", ("person.jpg", person[0], person[1]))] + [
                ("image[]", (f"product-{n}.jpg", content, ctype))
                for n, (content, ctype) in enumerate(products, start=1)
            ]
            data = {
                "model": self.model,
                "prompt": build_prompt(pieces),
                "size": _best_size(person[0]),
                "quality": self.quality,
                "output_format": "jpeg",
                "n": "1",
            }
            # input_fidelity keeps the person's face and the product's
            # detail, but not every model takes it. One that rejects it is
            # remembered: the rejection arrives only after the whole
            # multipart body — the photo and every product image — has been
            # uploaded, so asking again every time was uploading everything
            # twice for every render, on every job.
            if self.model not in _NO_INPUT_FIDELITY:
                data["input_fidelity"] = "high"
            resp = await self._post(client, data, files)
            if resp.status_code == 400 and "input_fidelity" in resp.text:
                logger.info("openai_image_no_input_fidelity", model=self.model)
                _NO_INPUT_FIDELITY.add(self.model)
                data.pop("input_fidelity", None)
                resp = await self._post(client, data, files)
        _raise_for_status(resp)
        try:
            b64 = resp.json()["data"][0]["b64_json"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise TryOnProviderError("OpenAI returned no image") from exc
        return TryOnOutput(
            image_bytes=base64.b64decode(b64),
            content_type="image/jpeg",
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    async def _post(self, client: httpx.AsyncClient, data: dict, files: list) -> httpx.Response:
        try:
            return await client.post(
                f"{self._base_url}/images/edits",
                headers={"Authorization": f"Bearer {self._api_key}"},
                data=data,
                files=files,
            )
        except httpx.RequestError as exc:
            raise TryOnProviderError(f"OpenAI request failed: {exc}", retryable=True) from exc


def _slot_from_category(category: str) -> str:
    return {"one-pieces": "dress", "tops": "top", "bottoms": "bottom"}.get(category, "top")


async def _download(client: httpx.AsyncClient, url: str, what: str) -> tuple[bytes, str]:
    if url.startswith("data:"):
        # the quality pipeline hands over its current image in memory
        header, _, payload = url.partition(",")
        ctype = header[5:].split(";")[0] or "image/jpeg"
        return base64.b64decode(payload), ctype if ctype in ("image/jpeg", "image/png", "image/webp") else "image/jpeg"
    try:
        resp = await client.get(url)
    except httpx.RequestError as exc:
        raise TryOnProviderError(f"Couldn't load {what}: {exc}", retryable=True) from exc
    if resp.status_code >= 400:
        raise TryOnProviderError(f"Couldn't load {what} (HTTP {resp.status_code})")
    ctype = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if ctype not in ("image/jpeg", "image/png", "image/webp"):
        ctype = "image/jpeg"
    return resp.content, ctype


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    try:
        message = resp.json().get("error", {}).get("message") or resp.text
    except ValueError:
        message = resp.text
    retryable = resp.status_code == 429 or resp.status_code >= 500
    raise TryOnProviderError(f"OpenAI image edit failed ({resp.status_code}): {message[:300]}", retryable=retryable)
