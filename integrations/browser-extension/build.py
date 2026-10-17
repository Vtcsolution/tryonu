"""Builds the two TryOnU browser extensions into ready-to-install zips:

    python integrations/browser-extension/build.py

- dist/shopper/  and  apps/web/public/downloads/tryonu-extension-shopper.zip
- dist/store/    and  apps/web/public/downloads/tryonu-extension-store.zip

Each package = its own files + the shared ones + icons + kind.js. The same
zip is what goes to the Chrome Web Store and Microsoft Edge Add-ons.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOWNLOADS = ROOT / "apps" / "web" / "public" / "downloads"
SHARED = ["api.js", "popup.css", "connect.js"]


def draw_icon(size: int) -> Image.Image:
    """The TryOnU mark: a white U with a dot, on the dark green rounded square."""
    s = 512
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=118, fill=(42, 51, 40, 255))
    white = (247, 245, 238, 255)
    w = 54  # stroke width
    left, right, top, bottom = 150, 362, 140, 382
    # the two arms
    d.rounded_rectangle((left - w // 2, top, left + w // 2, bottom - 106), radius=w // 2, fill=white)
    d.rounded_rectangle((right - w // 2, top, right + w // 2, bottom - 106), radius=w // 2, fill=white)
    # the bowl
    d.arc((left - w // 2, bottom - 238, right + w // 2, bottom + w // 2 - 2), start=0, end=180, fill=white, width=w)
    # the dot
    d.ellipse((s // 2 - 34, 236, s // 2 + 34, 304), fill=white)
    return img.resize((size, size), Image.LANCZOS)


def build(kind: str) -> Path:
    out = HERE / "dist" / kind
    if out.exists():
        shutil.rmtree(out)
    (out / "icons").mkdir(parents=True)
    for f in (HERE / kind).iterdir():
        shutil.copy(f, out / f.name)
    for name in SHARED:
        shutil.copy(HERE / "shared" / name, out / name)
    (out / "kind.js").write_text(f'globalThis.TRYONU_KIND = "{kind}";\n', encoding="utf-8")
    for size in (16, 32, 48, 128):
        draw_icon(size).save(out / "icons" / f"icon{size}.png")
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    zip_path = DOWNLOADS / f"tryonu-extension-{kind}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out).as_posix())
    return zip_path


if __name__ == "__main__":
    for kind in ("shopper", "store"):
        print("built", build(kind))
