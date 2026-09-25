"""Are the try-on engines actually reachable from this machine?

Run on the box that renders, with its own .env, because that is where
the answer matters: a key that works from a laptop says nothing about a
key that has not been pasted into the server's environment, and a model
name the account cannot reach fails the same way a wrong key does.

    ./.venv/bin/python scripts/check_engines.py                 # both
    ./.venv/bin/python scripts/check_engines.py --photo me.jpg  # a real person

Each engine gets one small edit and reports whether an image came back,
how long it took and how big it was. Nothing is written to the database
or to storage, and no key is printed.

Without --photo it uses a drawn placeholder, which checks the key, the
network and the model name but not much else: an engine that refuses to
edit photographs of real people will still answer a drawing. Point it at
a real photo to check that too.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.providers.base import OutfitPiece, TryOnProviderError  # noqa: E402
from app.core.config import get_settings  # noqa: E402

# a real listing, so the engines get a real garment rather than a swatch
PRODUCT = "https://i.ebayimg.com/images/g/j3EAAeSwBUdqfi52/s-l1600.jpg"
PRODUCT_NAME = "Pakistani Cotton Lawn 3PC Embroidered Shalwar Kameez"


def _placeholder() -> bytes:
    """A figure against a wall — enough for an engine to edit."""
    import cv2
    import numpy as np

    img = np.full((1536, 1024, 3), 232, np.uint8)
    cv2.rectangle(img, (0, 1330), (1024, 1536), (198, 205, 214), -1)  # floor
    cv2.ellipse(img, (512, 300), (120, 150), 0, 0, 360, (150, 170, 196), -1)  # head
    cv2.rectangle(img, (372, 450), (652, 1000), (120, 120, 130), -1)  # torso
    cv2.rectangle(img, (400, 1000), (624, 1330), (70, 70, 78), -1)  # legs
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise SystemExit("could not build the placeholder photo")
    return buf.tobytes()


async def _try(label: str, provider, photo: bytes) -> bool:  # noqa: ANN001
    piece = OutfitPiece(image_url=PRODUCT, slot="dress", name=PRODUCT_NAME)
    started = time.time()
    try:
        out = await provider.generate_outfit(
            "data:image/jpeg;base64," + base64.b64encode(photo).decode(), [piece]
        )
    except TryOnProviderError as exc:
        print(f"  {label:34s} FAILED after {time.time() - started:4.0f}s  {str(exc)[:120]}")
        return False
    except Exception as exc:  # noqa: BLE001 — this script's whole job is to report what broke
        print(f"  {label:34s} FAILED after {time.time() - started:4.0f}s  {type(exc).__name__}: {str(exc)[:100]}")
        return False

    size = ""
    try:
        import cv2
        import numpy as np

        img = cv2.imdecode(np.frombuffer(out.image_bytes, np.uint8), cv2.IMREAD_COLOR)
        size = f"{img.shape[1]}x{img.shape[0]}"
    except Exception:  # noqa: BLE001 — an unreadable image is still an answer
        size = "unreadable"
    print(
        f"  {label:34s} OK     {time.time() - started:4.0f}s  "
        f"{len(out.image_bytes) // 1024:5d} KB  {size}"
    )
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", help="a real full-body photo to edit; a placeholder is drawn without it")
    args = parser.parse_args()

    settings = get_settings()
    photo = Path(args.photo).read_bytes() if args.photo else _placeholder()
    print(f"photo:     {args.photo or 'drawn placeholder (checks keys and reachability only)'}")
    print(f"rendering with: VIRTUAL_TRYON_PROVIDER={settings.VIRTUAL_TRYON_PROVIDER}\n")

    results: list[bool] = []

    if settings.OPENAI_API_KEY:
        from app.ai.providers.openai_image import OpenAIImageTryOnProvider

        results.append(
            await _try(
                f"openai {settings.OPENAI_IMAGE_MODEL}",
                OpenAIImageTryOnProvider(
                    api_key=settings.OPENAI_API_KEY,
                    model=settings.OPENAI_IMAGE_MODEL,
                    quality=settings.OPENAI_IMAGE_QUALITY,
                ),
                photo,
            )
        )
    else:
        print("  openai                             SKIPPED  no OPENAI_API_KEY in this environment")

    if settings.GEMINI_API_KEY:
        from app.ai.providers.gemini_image import GeminiImageTryOnProvider

        results.append(
            await _try(
                f"gemini {settings.GEMINI_IMAGE_MODEL}",
                GeminiImageTryOnProvider(
                    api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_IMAGE_MODEL
                ),
                photo,
            )
        )
    else:
        print("  gemini                             SKIPPED  no GEMINI_API_KEY in this environment")

    print()
    if not results:
        print("neither engine is configured on this machine")
        return 2
    if all(results):
        print("both engines answered")
        return 0
    print("at least one engine did not answer — see above")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
