"""The "outfit receipt" picture for a Ready look: the model wearing the outfit
in the middle, each product in a framed box at the sides with its name and
price, and a thin line from each box to where the piece is worn. 1080 x 1350
(4:5), the size Instagram and Facebook posts use, so the same picture works on
tryonu.app and in ads."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1350
BG = (242, 240, 235)
INK = (28, 27, 23)
MUTED = (111, 108, 99)
SAGE = (87, 99, 79)
LINE = (186, 72, 72)  # the thin red guide lines of an outfit receipt
BOX_W, BOX_H = 230, 300  # one product: picture + name + price
TOP, BOTTOM = 130, 1250  # the area between the header and the footer band


@dataclass
class CardItem:
    name: str
    price: str  # "$57.69"
    image: bytes | None
    # where it is on the try-on picture (fractions), when known
    box: tuple[float, float, float, float] | None = None


# fonts with every currency sign (£, €): the server's DejaVu (Ubuntu), Windows'
# Segoe UI when developing, Pillow's own font as the last resort
_FONTS = {
    False: ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf"),
    True: ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in _FONTS[bold]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _person_box(img: Image.Image) -> tuple[int, int, int, int]:
    """Where the person is: everything that clearly differs from the studio
    backdrop (a soft gradient), with a little room around them."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    # the backdrop, row by row: the average of the far left and far right edges
    small = rgb.resize((max(1, w // 8), max(1, h // 8)))
    sw, sh = small.size
    px = small.load()
    mask = Image.new("L", (sw, sh), 0)
    mp = mask.load()
    for y in range(sh):
        edge = [px[x, y] for x in (0, 1, sw - 2, sw - 1)]
        bg = tuple(sum(c[i] for c in edge) / len(edge) for i in range(3))
        for x in range(sw):
            r, g, b = px[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > 60:
                mp[x, y] = 255
    mask = mask.filter(ImageFilter.MinFilter(3))  # drop specks of noise
    box = mask.getbbox()
    if not box:
        return 0, 0, w, h
    x0, y0, x1, y1 = (v * 8 for v in box)
    mx, my = int((x1 - x0) * 0.12), int((y1 - y0) * 0.04)
    return max(0, x0 - mx), max(0, y0 - my), min(w, x1 + mx), min(h, y1 + my)


# roughly where a kind of piece is worn, as a fraction of the person's height
# (head to feet), for pieces the try-on didn't locate
_BODY = (
    (("hat", "beanie", "cap", "tikka", "headband", "turban"), 0.06),
    (("earring", "jhumka", "sunglasses", "glasses"), 0.11),
    (("scarf", "necklace", "choker", "muffler", "tie"), 0.2),
    (("watch", "bracelet", "bangle", "ring", "glove", "mitten"), 0.5),
    (("bag", "clutch", "tote", "purse", "handbag"), 0.55),
    (("trouser", "jean", "pant", "chino", "skirt", "legging", "shalwar", "palazzo"), 0.68),
    (("boot", "shoe", "sneaker", "heel", "sandal", "khussa", "loafer", "chappal", "slipper"), 0.94),
)


def _height_on_body(name: str) -> float:
    low = name.lower()
    for words, y in _BODY:
        if any(w in low for w in words):
            return y
    return 0.36  # coats, jackets, sweaters, dresses, shirts: the upper body


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
    """The whole picture inside w x h, on white (product photos come in every shape)."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((w, h), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), "white")
    canvas.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
    return canvas


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int, lines: int) -> list[str]:
    words, out, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
            continue
        if line:
            out.append(line)
        line = word
        if len(out) == lines:
            break
    if line and len(out) < lines:
        out.append(line)
    if len(out) == lines and " ".join(out) != text:
        last = out[-1]
        while last and draw.textlength(last + "…", font=font) > width:
            last = last[:-1]
        out[-1] = last.rstrip() + "…"
    return out


def render_card(title: str, person: bytes, items: list[CardItem]) -> bytes:
    full = ImageOps.exif_transpose(Image.open(io.BytesIO(person))).convert("RGB")
    crop_x0, crop_y0, cx1, cy1 = _person_box(full)
    person_img = full.crop((crop_x0, crop_y0, cx1, cy1))
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    # header
    small, big = _font(24), _font(40, bold=True)
    label = "OUTFIT RECEIPT  ·  TRYONU"
    draw.text(((W - draw.textlength(label, font=small)) / 2, 34), label, font=small, fill=MUTED)
    t = _wrap(draw, title, big, W - 160, 1)[0] if title else ""
    draw.text(((W - draw.textlength(t, font=big)) / 2, 70), t, font=big, fill=INK)

    # the model, as big as the middle column allows, as a rounded photo
    col_w, col_h = 540, BOTTOM - TOP - 10
    scale = min(col_w / person_img.width, col_h / person_img.height)
    pw, ph = int(person_img.width * scale), int(person_img.height * scale)
    person_img = _rounded(person_img.resize((pw, ph), Image.LANCZOS), 26)
    px, py = (W - pw) // 2, TOP + (col_h - ph) // 2
    canvas.paste(person_img, (px, py), person_img)

    def on_person(fx: float, fy: float) -> tuple[float, float]:
        """A point given as fractions of the full try-on picture, on the card."""
        return px + (fx * full.width - crop_x0) * scale, py + (fy * full.height - crop_y0) * scale

    def target(item: CardItem, side: str) -> tuple[float, float]:
        """Where on the model the line for this piece ends."""
        if item.box:
            bx0, by0, bx1, by1 = item.box
            return on_person(bx0 if side == "left" else bx1, (by0 + by1) / 2)
        return px + (0.42 if side == "left" else 0.58) * pw, py + _height_on_body(item.name) * ph

    # products at the sides, ordered head to feet so the lines don't cross:
    # left column takes every other piece, the right column the rest
    shown = sorted(items[:6], key=lambda it: ((it.box[1] + it.box[3]) / 2) if it.box else _height_on_body(it.name))
    left, right = shown[0::2], shown[1::2]
    item_font, price_font = _font(19), _font(22, bold=True)

    def column(group: list[CardItem], x: int, side: str) -> None:
        if not group:
            return
        gap = (BOTTOM - TOP - len(group) * BOX_H) / (len(group) + 1)
        for i, item in enumerate(group):
            y = int(TOP + gap + i * (BOX_H + gap))
            if item.image:
                try:
                    pic = _fit(Image.open(io.BytesIO(item.image)), BOX_W - 20, 180)
                    canvas.paste(pic, (x + 10, y + 10))
                except Exception:  # noqa: BLE001 - a broken product photo leaves its box empty
                    pass
            draw.rectangle((x, y, x + BOX_W, y + 200), outline=LINE, width=2)
            ty = y + 210
            for line in _wrap(draw, item.name, item_font, BOX_W, 2):
                draw.text((x, ty), line, font=item_font, fill=INK)
                ty += 24
            draw.text((x, ty + 2), item.price, font=price_font, fill=SAGE)
            # a line from the box to where the piece is worn
            tx, ty2 = target(item, side)
            sx = x + BOX_W if side == "left" else x
            draw.line((sx, y + 100, tx, ty2), fill=LINE, width=2)
            draw.ellipse((tx - 5, ty2 - 5, tx + 5, ty2 + 5), fill=LINE)

    column(left, 24, "left")
    column(right, W - 24 - BOX_W, "right")

    # footer band: the call to action
    draw.rectangle((0, H - 90, W, H), fill=SAGE)
    cta = "Try this look on you first  ·  tryonu.app"
    cf = _font(30, bold=True)
    draw.text(((W - draw.textlength(cta, font=cf)) / 2, H - 64), cta, font=cf, fill=(255, 255, 255))

    out = io.BytesIO()
    canvas.save(out, "JPEG", quality=88, optimize=True, progressive=True)
    return out.getvalue()
