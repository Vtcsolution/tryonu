"""The end-of-look check: is every selected product still there in the FINAL image?

Each step was already verified when it was drawn. That says nothing about
whether a later product covered or altered it, so the final image is
checked against every step:

* persistence (always, free): the region a product changed when it was
  drawn must still look like that step's own output in the final image.
* the vision inspector (TRYON_DIRECT_VLM_QC, a paid OpenAI call): every
  retailer photo, the customer's original photo and the final image, asked
  per product whether it is present, the right colour, its distinctive
  details kept and correctly placed, and whether the person is the same.

A product either verifies or is REVIEW_REQUIRED. Nothing here produces a
percentage, and nothing here changes the image.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.logging import logger

VERIFIED = "verified"
REVIEW_REQUIRED = "review_required"

# per-pixel colour difference (0..1) counted as "different"
_PIXEL_THRESHOLD = 0.12
# share of a product's own region allowed to differ in the final image
_MAX_REGION_CHANGED = 0.35
_WORK_SIDE = 512

_VLM_INSTRUCTIONS = (
    "You are checking a virtual try-on. You get the customer's ORIGINAL photo, the FINAL try-on image, and "
    "numbered reference photos of the exact retail products that were supposed to be put on the customer. "
    "Judge each numbered product against the FINAL image only. Reply with JSON only: "
    '{"same_person": true|false, "identity_note": "short", "products": [{"index": <number>, '
    '"present": true|false, "color_correct": true|false, "details_preserved": true|false, '
    '"placement_correct": true|false, "note": "short, concrete"}]}. '
    "present = this exact product is visibly worn or carried, not a similar one. If you cannot see it clearly, "
    "answer false. Do not guess. placement_correct = worn or carried naturally on the right body part, at real "
    "scale and perspective, behind or under what should cover it; a product that looks pasted on like a flat "
    "sticker, floats, or sits in front of a floor-length outfit instead of on the feet is false; so is a product held by an extra hand "
    "or arm that is not the customer's own, or one given parts it does not have (a chain added to a plain nose "
    "ring)."
)


def _decode(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    return img


def _work(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def region_still_present(step_output: bytes, final: bytes, bbox: list[float] | None) -> dict:
    """Whether the region one product changed is unchanged in the final image."""
    if not bbox:
        return {"status": REVIEW_REQUIRED, "reason": "no changed region was measured for this product"}
    try:
        step_img, final_img = _decode(step_output), _decode(final)
    except ValueError as exc:
        return {"status": REVIEW_REQUIRED, "reason": f"could not read an image: {exc}"}
    h, w = step_img.shape[:2]
    scale = _WORK_SIDE / max(h, w)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    a, b = _work(step_img, size), _work(final_img, size)
    x0, y0, x1, y1 = bbox
    px0, py0 = int(x0 * size[0]), int(y0 * size[1])
    px1, py1 = max(px0 + 1, int(x1 * size[0])), max(py0 + 1, int(y1 * size[1]))
    diff = np.abs(a[py0:py1, px0:px1] - b[py0:py1, px0:px1]).mean(axis=2)
    changed = float((diff > _PIXEL_THRESHOLD).mean())
    if changed > _MAX_REGION_CHANGED:
        return {
            "status": REVIEW_REQUIRED,
            "region_changed_fraction": round(changed, 4),
            "reason": "a later product covered or altered this product's area",
        }
    return {"status": VERIFIED, "region_changed_fraction": round(changed, 4)}


async def vlm_final_check(original: bytes, final: bytes, product_images: list[bytes], names: list[str]) -> dict:
    """One paid OpenAI vision call over the whole look. Never raises."""
    from app.services.tryon_quality.vision import ask_json, image_part

    try:
        content: list[dict] = [
            {"type": "text", "text": "ORIGINAL customer photo:"},
            image_part(_decode(original), 768),
            {"type": "text", "text": "FINAL try-on image:"},
            image_part(_decode(final), 1536),
        ]
        for i, (data, name) in enumerate(zip(product_images, names)):
            content += [{"type": "text", "text": f"Product {i}: {name}"}, image_part(_decode(data), 512)]
        answer = await ask_json(_VLM_INSTRUCTIONS, content)
    except Exception as exc:  # noqa: BLE001 — an unreadable check is "cannot confirm", never "passed"
        logger.warning("tryon_final_vlm_failed", error=str(exc)[:200])
        return {"enabled": True, "error": str(exc)[:200], "products": [], "same_person": None}
    return {"enabled": True, **answer}


def _vlm_verdict(vlm: dict, index: int) -> dict | None:
    for row in vlm.get("products") or []:
        if isinstance(row, dict) and row.get("index") == index:
            return row
    return None


async def final_check(
    original: bytes,
    final: bytes,
    step_outputs: list[bytes],
    bboxes: list[list[float] | None],
    product_images: list[bytes],
    names: list[str],
    *,
    with_vlm: bool,
) -> dict:
    """Per-product final status, plus whether the whole look verified."""
    products = []
    for i, (output, bbox) in enumerate(zip(step_outputs, bboxes)):
        if i == len(step_outputs) - 1:
            products.append({"index": i, "name": names[i], "status": VERIFIED, "persistence": "last product"})
        else:
            persistence = region_still_present(output, final, bbox)
            products.append({"index": i, "name": names[i], "status": persistence["status"], "persistence": persistence})

    vlm: dict = {"enabled": False}
    if with_vlm:
        vlm = await vlm_final_check(original, final, product_images, names)
        for row in products:
            verdict = _vlm_verdict(vlm, row["index"])
            row["vlm"] = verdict
            checks = ("present", "color_correct", "details_preserved", "placement_correct")
            if verdict is None or not all(verdict.get(k) is True for k in checks):
                row["status"] = REVIEW_REQUIRED
                row.setdefault("reasons", []).append(
                    "the vision check could not confirm this product"
                    if verdict is None
                    else "the vision check flagged: " + ", ".join(k for k in checks if verdict.get(k) is not True)
                )

    identity_ok = vlm.get("same_person") is not False if with_vlm else True
    passed = identity_ok and all(row["status"] == VERIFIED for row in products)
    return {"passed": passed, "identity_ok": identity_ok, "products": products, "vlm": vlm}
