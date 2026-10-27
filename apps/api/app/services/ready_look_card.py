"""The "outfit receipt" picture for a Ready look: the try-on picture fills the
whole frame, and each product sits in a card on the left or right edge
("1. Sunglasses", its photo and price) with a thin line to where it's worn.
1080 x 1350 (4:5), the size Instagram and Facebook posts use.

The same layout (where the picture, each card and each line go) is returned
with the picture, so tryonu.app can draw the cards as links over the try-on
picture: the names readable and every product a tap away."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1350
BAND = 84  # the call-to-action band at the bottom
MARGIN = 22  # cards from the frame's edges
INK = (28, 27, 23)
SAGE = (87, 99, 79)
CARD_BG = (252, 249, 246)


@dataclass
class CardItem:
    name: str
    price: str  # "$57.69"
    image: bytes | None
    # where it is on the try-on picture (fractions), when known
    box: tuple[float, float, float, float] | None = None


# fonts with every currency sign (£, €): the server's DejaVu (Ubuntu), Windows'
# Segoe UI / Georgia when developing, Pillow's own font as the last resort
_FONTS: dict[bool | str, tuple[str, ...]] = {
    False: ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf"),
    True: ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    "serif": ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "C:/Windows/Fonts/georgiab.ttf"),
}


def _font(size: int, bold: bool | str = False) -> ImageFont.FreeTypeFont:
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
    (("hat", "beanie", "cap", "tikka", "headband", "turban"), 0.04),
    (("earring", "jhumka", "sunglasses", "glasses"), 0.09),
    (("scarf", "necklace", "choker", "muffler", "tie"), 0.19),
    (("watch", "bracelet", "bangle", "ring", "glove", "mitten"), 0.5),
    (("bag", "clutch", "tote", "purse", "handbag"), 0.55),
    (("trouser", "jean", "pant", "chino", "skirt", "legging", "shalwar", "palazzo"), 0.68),
    (("boot", "shoe", "sneaker", "heel", "sandal", "khussa", "loafer", "chappal", "slipper", "trainer", "court vision"), 0.95),
)


def _height_on_body(name: str) -> float:
    low = name.lower()
    for words, y in _BODY:
        if any(w in low for w in words):
            return y
    return 0.33  # coats, jackets, sweaters, dresses, shirts: the upper body


# a short name for each piece ("Sunglasses", "Puffer Jacket"): shop titles are
# long and keyword-stuffed, so the word that comes first in the title wins
_LABELS: list[tuple[str, tuple[str, ...]]] = [
    ("Sunglasses", ("sunglasses", "sunglass", "shades")),
    ("Glasses", ("glasses", "eyeglasses", "spectacles", "eyewear")),
    ("Watch", ("watch", "watches", "smartwatch", "wristwatch")),
    ("Maang Tikka", ("maang tikka", "tikka", "matha patti")),
    ("Earrings", ("earring", "earrings", "jhumka", "jhumkas", "jhumki", "studs", "chandbali")),
    ("Necklace", ("necklace", "necklaces", "choker", "pendant", "mala")),
    ("Rings", ("ring", "rings")),
    ("Bracelet", ("bracelet", "bracelets", "bangle", "bangles", "kara")),
    ("Clutch Bag", ("clutch", "potli")),
    ("Bag", ("bag", "bags", "handbag", "handbags", "purse", "tote", "backpack", "satchel")),
    ("Scarf", ("scarf", "scarves", "muffler", "stole", "snood")),
    ("Shawl", ("shawl", "pashmina")),
    ("Cap", ("cap", "caps", "beanie", "beanies")),
    ("Hat", ("hat", "hats", "fedora")),
    ("Belt", ("belt", "belts")),
    ("Gloves", ("gloves", "mittens")),
    ("Tie", ("tie", "necktie", "bow tie")),
    ("Dupatta", ("dupatta", "dupattas", "chunri")),
    ("Shalwar Kameez", ("shalwar kameez", "salwar kameez", "salwar suit", "kameez", "shalwar", "salwar", "3pc", "3 piece", "2pc", "2 piece")),
    ("Lehenga", ("lehenga", "lehengas", "ghagra")),
    ("Sharara", ("sharara", "gharara")),
    ("Saree", ("saree", "sarees", "sari")),
    ("Sherwani", ("sherwani", "achkan")),
    ("Kurta", ("kurta", "kurtas", "kurti", "kurtis")),
    ("Waistcoat", ("waistcoat", "vest", "gilet")),
    ("Dress", ("dress", "dresses", "gown", "gowns", "frock", "frocks", "maxi", "anarkali", "pishwas", "jumpsuit", "abaya")),
    ("Suit", ("suit", "suits", "tuxedo")),
    ("Blazer", ("blazer", "blazers", "sport coat")),
    ("Puffer Jacket", ("puffer", "puffer jacket", "down jacket", "quilted jacket", "padded jacket")),
    ("Jacket", ("jacket", "jackets", "bomber", "parka", "windbreaker", "anorak")),
    ("Coat", ("coat", "coats", "overcoat", "trench", "peacoat")),
    ("Cardigan", ("cardigan", "cardigans")),
    ("Hoodie", ("hoodie", "hoodies", "sweatshirt", "sweatshirts")),
    ("Sweater", ("sweater", "sweaters", "jumper", "pullover", "turtleneck", "knitwear")),
    ("T-shirt", ("t-shirt", "t-shirts", "tshirt", "tee", "tees")),
    ("Polo Shirt", ("polo",)),
    ("Shirt", ("shirt", "shirts", "blouse", "blouses")),
    ("Top", ("crop top", "tank top", "tops", "tunic")),
    ("Jeans", ("jeans", "jean", "denims")),
    ("Trousers", ("trouser", "trousers", "pant", "pants", "chinos", "chino", "slacks", "joggers")),
    ("Shorts", ("shorts",)),
    ("Skirt", ("skirt", "skirts")),
    ("Leggings", ("leggings", "tights")),
    ("Khussa", ("khussa", "khussas", "jutti", "juttis", "mojari", "nagra")),
    ("Sneakers", ("sneaker", "sneakers", "trainers", "trainer", "running shoes", "court vision", "air force 1", "air max")),
    ("Boots", ("boot", "boots")),
    ("Heels", ("heels", "heel", "pumps", "stilettos")),
    ("Sandals", ("sandal", "sandals", "chappal", "chappals", "peshawari", "kolhapuri", "slides")),
    ("Loafers", ("loafer", "loafers", "moccasins")),
    ("Shoes", ("shoe", "shoes", "flats", "oxfords", "derby")),
    ("Bridal Makeup", ("lipstick", "makeup", "eyeshadow", "foundation")),
    ("Perfume", ("perfume", "fragrance", "attar")),
]
_LABEL_RE = [
    (label, re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b"))
    for label, words in _LABELS
]


def short_label(name: str, extra: str | None = None) -> str:
    """The kind of piece, in a word or two, for its card ("Sunglasses")."""
    for text in (name, extra or ""):
        low = text.lower()
        hits = [(m.start(), -len(m.group(0)), label) for label, rx in _LABEL_RE for m in rx.finditer(low)]
        if hits:
            return min(hits)[2]
    words = [w for w in re.split(r"[\s,|/-]+", name) if w.isalpha()]
    return " ".join(words[:2]).title() or "Piece"


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


def _feathered(img: Image.Image, edge: int) -> Image.Image:
    """The picture with soft edges, so it melts into the blurred backdrop."""
    w, h = img.size
    mask = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(mask)
    for i in range(edge):
        draw.rectangle((i, i, w - 1 - i, h - 1 - i), outline=int(255 * (i + 1) / (edge + 1)))
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def _layout(full: Image.Image, items: list[CardItem]) -> dict:
    """Where everything goes on the 1080 x 1350 frame (see the module docstring)."""
    w, h = full.size
    bx0, by0, bx1, by1 = _person_box(full)
    area_h = H - BAND
    # the person as tall as the frame above the band allows (feet never under
    # it), centred, and the picture filling the frame where it can
    cover = max(W / w, area_h / h)
    scale = min((area_h - 24) / max(1, by1 - by0), cover * 2.2)
    iw, ih = w * scale, h * scale
    ix = W / 2 - (bx0 + bx1) / 2 * scale
    iy = 12 - by0 * scale
    ix = min(0, max(W - iw, ix)) if iw >= W else (W - iw) / 2
    iy = min(0, max(area_h - ih, iy)) if ih >= area_h else (area_h - ih) / 2

    # the person themself (the box has room around them)
    pw, ph = (bx1 - bx0) / 1.24, (by1 - by0) / 1.08
    pcx, ptop = (bx0 + bx1) / 2, by0 + (by1 - by0 - ph) / 2

    def at(fx: float, fy: float) -> tuple[float, float]:
        return ix + fx * scale, iy + fy * scale

    def anchor(item: CardItem, side: str) -> tuple[float, float]:
        if item.box:
            x0, y0, x1, y1 = item.box
            return at((x0 + (x1 - x0) * (0.3 if side == "left" else 0.7)) * w, (y0 + y1) / 2 * h)
        return at(pcx + (-0.14 if side == "left" else 0.14) * pw, ptop + _height_on_body(item.name) * ph)

    order = sorted(
        range(len(items)),
        key=lambda i: ((items[i].box[1] + items[i].box[3]) / 2) if items[i].box else _height_on_body(items[i].name),
    )
    # both columns run head to feet, so the lines stay short and don't cross
    tiles = []
    number = 1
    for side, group in (("left", order[0::2]), ("right", order[1::2])):
        if not group:
            continue
        n = len(group)
        top, bottom = 20, area_h - 20
        th = min(300, (bottom - top - (n - 1) * 16) / n)
        tw = min(250, th * 0.8)
        gap = (bottom - top - n * th) / (n + 1)
        x = MARGIN if side == "left" else W - MARGIN - tw
        for k, i in enumerate(group):
            y = top + gap + k * (th + gap)
            label_h = max(54, th * 0.22)
            pic = (x + 8, y + 8, tw - 16, th - label_h - 8)
            ax, ay = anchor(items[i], side)
            sx = x + tw if side == "left" else x
            tiles.append({
                "item": i,
                "n": number,
                "label": short_label(items[i].name),
                "price": items[i].price,
                "box": [round(v, 1) for v in (x, y, tw, th)],
                "img": [round(v, 1) for v in pic],
                "line": [[round(sx, 1), round(pic[1] + pic[3] / 2, 1)], [round(ax, 1), round(ay, 1)]],
            })
            number += 1
    return {"w": W, "h": H, "band": BAND, "image": [round(v, 1) for v in (ix, iy, iw, ih)], "tiles": tiles}


def render_card(title: str, person: bytes, items: list[CardItem]) -> tuple[bytes, dict]:  # noqa: ARG001 - the page shows the title
    """The picture (JPEG) and its layout."""
    full = ImageOps.exif_transpose(Image.open(io.BytesIO(person))).convert("RGB")
    items = items[:10]
    lay = _layout(full, items)
    ix, iy, iw, ih = lay["image"]

    # a soft, darker copy of the picture behind, then the try-on picture itself
    frame = Image.new("RGB", (W, H), SAGE)
    backdrop = ImageOps.fit(full, (W, H - BAND), Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    frame.paste(ImageEnhance.Brightness(backdrop).enhance(0.96), (0, 0))
    sharp = _feathered(full.resize((max(1, round(iw)), max(1, round(ih))), Image.LANCZOS), 56)
    picture = Image.new("RGBA", (W, H - BAND), (0, 0, 0, 0))
    picture.paste(sharp, (round(ix), round(iy)), sharp)
    frame.paste(picture, (0, 0), picture)
    canvas = frame.convert("RGBA")

    # lines under the cards: a faint dark shadow, then white, then the dot
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    for t in lay["tiles"]:
        (sx, sy), (ax, ay) = t["line"]
        ld.line((sx, sy + 1, ax, ay + 1), fill=(0, 0, 0, 90), width=5)
    lines = lines.filter(ImageFilter.GaussianBlur(1.5))
    ld = ImageDraw.Draw(lines)
    for t in lay["tiles"]:
        (sx, sy), (ax, ay) = t["line"]
        ld.line((sx, sy, ax, ay), fill=(255, 255, 255, 235), width=3)
        ld.ellipse((ax - 9, ay - 9, ax + 9, ay + 9), fill=(255, 255, 255, 255), outline=(40, 40, 40, 160), width=2)
        ld.ellipse((ax - 3, ay - 3, ax + 3, ay + 3), fill=SAGE + (255,))
    canvas = Image.alpha_composite(canvas, lines)

    # the cards, each with a soft shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for t in lay["tiles"]:
        x, y, tw, th = t["box"]
        sd.rounded_rectangle((x + 2, y + 6, x + tw + 2, y + th + 6), radius=20, fill=(0, 0, 0, 70))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(8)))
    draw = ImageDraw.Draw(canvas)
    for t in lay["tiles"]:
        x, y, tw, th = t["box"]
        draw.rounded_rectangle((x, y, x + tw, y + th), radius=20, fill=CARD_BG + (255,), outline=(226, 214, 206, 255), width=2)
        px, py, pw, ph = (round(v) for v in t["img"])
        item = items[t["item"]]
        pic = Image.new("RGB", (pw, ph), "white")
        if item.image:
            try:
                pic = _fit(Image.open(io.BytesIO(item.image)), pw, ph)
            except Exception:  # noqa: BLE001 - a broken product photo leaves its box empty
                pass
        rounded = _rounded(pic, 14)
        canvas.paste(rounded, (px, py), rounded)
        # "1. Sunglasses" and the price, centred under the photo, never cut off
        text = f"{t['n']}. {t['label']}"
        label_top, label_h = py + ph, y + th - (py + ph)
        size = max(16, round(label_h * 0.36))
        f = _font(size, "serif")
        while draw.textlength(text, font=f) > tw - 16 and size > 13:
            size -= 1
            f = _font(size, "serif")
        pf = _font(max(14, round(size * 0.8)), bold=True)
        ty = label_top + (label_h - (size + 6 + pf.size)) / 2
        draw.text((x + (tw - draw.textlength(text, font=f)) / 2, ty), text, font=f, fill=INK)
        draw.text((x + (tw - draw.textlength(t["price"], font=pf)) / 2, ty + size + 6), t["price"], font=pf, fill=SAGE)

    # the call to action
    draw.rectangle((0, H - BAND, W, H), fill=SAGE)
    cta = "Try this look on you first  ·  tryonu.app"
    cf = _font(30, bold=True)
    draw.text(((W - draw.textlength(cta, font=cf)) / 2, H - BAND + (BAND - 36) / 2), cta, font=cf, fill=(255, 255, 255))

    out = io.BytesIO()
    canvas.convert("RGB").save(out, "JPEG", quality=88, optimize=True, progressive=True)
    return out.getvalue(), lay
