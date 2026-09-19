"""OpenAI vision calls used by the try-on quality pipeline — looking at
images, never drawing them: understanding the product photo, locating the
worn item in a render, and grading the result."""

from __future__ import annotations

import base64
import json

import cv2
import httpx
import numpy as np

from app.core.config import get_settings


class VisionError(Exception):
    pass


def image_part(img: np.ndarray, max_side: int = 1024, detail: str = "high") -> dict:
    h, w = img.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    url = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
    return {"type": "image_url", "image_url": {"url": url, "detail": detail}}


async def ask_json(instructions: str, content: list[dict], *, timeout: float = 120.0) -> dict:
    """One chat-completions call with images, answered as a JSON object."""
    s = get_settings()
    if not s.OPENAI_API_KEY:
        raise VisionError("no OpenAI API key")
    body = {
        "model": s.OPENAI_VISION_MODEL,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_object"},
    }
    if s.OPENAI_VISION_MODEL.startswith(("gpt-5", "o")):
        body["reasoning_effort"] = "low"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {s.OPENAI_API_KEY}"},
                json=body,
            )
    except httpx.RequestError as exc:
        raise VisionError(f"vision request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise VisionError(f"vision request failed ({resp.status_code}): {resp.text[:300]}")
    try:
        return json.loads(resp.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError, ValueError) as exc:
        raise VisionError("vision reply wasn't JSON") from exc
