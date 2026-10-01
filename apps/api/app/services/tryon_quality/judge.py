"""Grade a try-on before it's returned — so a poor render is retried or
refused instead of being reported as a success.

Identity isn't asked of the vision model: the merge keeps the person's
own pixels outside the product area on purpose, and masked.py's real API
mask enforces the same thing more strongly still. Neither is checked by
pixel measurement here — tried once, on masked.py's own before/after: a
plain colour diff between the customer's (usually smaller) original
photo and the model's own generation reads as 20-50% "changed" even on a
visually-confirmed-correct render, because upscaling the small original
to compare is blurrier than a fresh render at every pixel, protected or
not. That number measures resolution mismatch, not a broken mask. The
vision model grades what only it can: is this the exact product, is it
worn the way a real one would be, does it look like a photograph."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.services.tryon_quality.compose import Region
from app.services.tryon_quality.vision import VisionError, ask_json, image_part

_INSTRUCTIONS = (
    "You are a strict quality inspector for virtual try-on photos. You get: (1) the product reference photo, "
    "(2) the person BEFORE, cropped to where the product goes, (3) the person AFTER, same crop, (4) the whole "
    "AFTER photo. Judge ONLY the product being tried on. The reference PHOTO is the ground truth — the text "
    "description is only a hint and may be wrong. Judge details at the resolution the AFTER photo allows: don't "
    "mark down a logo or dial text simply for being too small to read at this size, but do mark down wrong "
    "colours, shapes, patterns or hardware. Reply with JSON only:\n"
    '{"product_match": 0-10 (is it the SAME product as the reference: colour, pattern, print/logo, material, '
    "shape, buttons/zips/hardware, dial/strap, sole — 10 identical, 7 minor detail drift, 4 similar-looking "
    'but different product, 0 wrong or missing), '
    '"worn_correctly": 0-10 (placed where it belongs and fitted to THIS body and pose: garment covers the torso/'
    "legs with correct shoulders, sleeves, collar, waist and hem; watch wraps AROUND the wrist in perspective, "
    "not flat; shoes on the correct feet with correct perspective and ground contact; bag strap follows the "
    'shoulder/body; proportions realistic), '
    '"realism": 0-10 (lighting, shadows and occlusion consistent with the photo, no pasted-on look, no seams, '
    'halos, duplicated limbs, warped hands or other artifacts), '
    '"issues": ["short concrete problems, empty if none"], '
    '"fix": "one short instruction to the try-on model that would fix the most important problem, or empty"}'
)


@dataclass(frozen=True, slots=True)
class Verdict:
    product_match: float
    worn_correctly: float
    realism: float
    issues: list[str] = field(default_factory=list)
    fix: str = ""

    @property
    def score(self) -> float:
        return self.product_match * 0.45 + self.worn_correctly * 0.35 + self.realism * 0.2

    def passes(self, min_product: float, min_other: float) -> bool:
        return (
            self.product_match >= min_product
            and self.worn_correctly >= min_other
            and self.realism >= min_other
        )


def _dominant_lab(img: np.ndarray) -> tuple[float, float, float]:
    """The median L*a*b* of `img`'s pixels, excluding a white/light-grey
    studio backdrop.

    A product photo is almost always shot on exactly that backdrop, and
    it is usually the majority of the frame by area — splitting on
    "more/less saturated than this image's own median" breaks exactly
    when the product is the minority of pixels, since the median then
    falls inside the background itself. Excluding on bright-AND-neutral
    together, instead, targets a white/grey backdrop specifically,
    whatever colour the product is — including a black or grey product,
    which a saturation-only split would have excluded too."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    lightness = lab[..., 0]
    a, b = lab[..., 1] - 128.0, lab[..., 2] - 128.0
    saturation = np.hypot(a, b)
    backdrop = (lightness > 200) & (saturation < 10)
    keep = ~backdrop
    if keep.sum() < 50:
        keep = np.ones_like(keep, dtype=bool)
    return tuple(float(np.median(lab[..., c][keep])) for c in range(3))


def _delta_e_ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    """Perceptual colour distance (Sharma et al., 2005) between two L*a*b*
    colours — a shift in a saturated colour reads as smaller than the
    same raw numeric distance in a near-neutral one, matching how a
    person actually perceives it. 0 = identical; roughly 10+ is a colour
    a shopper would call "wrong", not just "a bit off"."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    cbar = (c1 + c2) / 2.0
    g = 0.5 * (1 - math.sqrt(cbar**7 / (cbar**7 + 25.0**7))) if cbar > 0 else 0.0
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0.0

    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0:
        dhp_deg = 0.0
    else:
        dhp_deg = h2p - h1p
        if dhp_deg > 180:
            dhp_deg -= 360
        elif dhp_deg < -180:
            dhp_deg += 360
    dHp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp_deg) / 2)

    lbarp = (l1 + l2) / 2
    cbarp = (c1p + c2p) / 2
    if c1p * c2p == 0:
        hbarp = h1p + h2p
    else:
        hsum, hdiff = h1p + h2p, abs(h1p - h2p)
        if hdiff <= 180:
            hbarp = hsum / 2
        elif hsum < 360:
            hbarp = (hsum + 360) / 2
        else:
            hbarp = (hsum - 360) / 2

    t = (
        1
        - 0.17 * math.cos(math.radians(hbarp - 30))
        + 0.24 * math.cos(math.radians(2 * hbarp))
        + 0.32 * math.cos(math.radians(3 * hbarp + 6))
        - 0.20 * math.cos(math.radians(4 * hbarp - 63))
    )
    d_theta = 30 * math.exp(-(((hbarp - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cbarp**7 / (cbarp**7 + 25.0**7)) if cbarp > 0 else 0.0
    sl = 1 + (0.015 * (lbarp - 50) ** 2) / math.sqrt(20 + (lbarp - 50) ** 2)
    sc = 1 + 0.045 * cbarp
    sh = 1 + 0.015 * cbarp * t
    rt = -math.sin(math.radians(2 * d_theta)) * rc

    return math.sqrt(
        (dlp / sl) ** 2 + (dcp / sc) ** 2 + (dHp / sh) ** 2 + rt * (dcp / sc) * (dHp / sh)
    )


# Below this, a colour difference reads as "a slightly different light",
# not "a different product" — measured against the live job that showed
# one product's colour drift to resemble another's selected colour.
_COLOR_FAIL_DELTA_E = 18.0


def color_mismatch(result_crop: np.ndarray, product: np.ndarray) -> float | None:
    """How far the result's own dominant colour is from the product
    photo's, as a perceptual CIEDE2000 distance. None only when there
    isn't enough of either image to form an estimate (never asks what
    kind of product this is)."""
    return _delta_e_ciede2000(_dominant_lab(result_crop), _dominant_lab(product))


def _local_lab_diff(a: np.ndarray, b: np.ndarray, blur: float = 1.5) -> np.ndarray:
    la = cv2.cvtColor(cv2.GaussianBlur(a, (0, 0), blur), cv2.COLOR_BGR2LAB).astype(np.float32)
    lb = cv2.cvtColor(cv2.GaussianBlur(b, (0, 0), blur), cv2.COLOR_BGR2LAB).astype(np.float32)
    return np.linalg.norm(la - lb, axis=2)


def region_was_touched(before: np.ndarray, after: np.ndarray, *, min_share: float = 0.06) -> bool:
    """Whether a real, contiguous part of this crop changed between before
    and after — not the resampling/re-encoding noise a correctly-rendered
    crop already shows on its own (this module's own docstring measured
    that at 20-50% on a visually-confirmed-correct render when read as a
    bare whole-image average). Blob-based, the same approach find_changes
    already uses successfully elsewhere, rather than a plain mean a
    genuinely untouched crop can clear on noise alone."""
    if before.shape[:2] != after.shape[:2]:
        after = cv2.resize(after, (before.shape[1], before.shape[0]), interpolation=cv2.INTER_AREA)
    diff = _local_lab_diff(before, after)
    changed = (diff > 20.0).astype(np.uint8)
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    return bool(changed.sum() / changed.size >= min_share)


def _crop(img: np.ndarray, region: Region, pad: float = 0.6) -> np.ndarray:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = region.pixels(w, h, pad)
    crop = img[y0:y1, x0:x1]
    # a watch crop from a full-body photo is ~100px; shown that small the
    # inspector only ever answered "too small to verify" — enlarge it
    ch, cw = crop.shape[:2]
    if 0 < max(ch, cw) < 640:
        scale = 640 / max(ch, cw)
        crop = cv2.resize(crop, (round(cw * scale), round(ch * scale)), interpolation=cv2.INTER_CUBIC)
    return crop


def _num(value: object) -> float:
    try:
        return max(0.0, min(10.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


_SMALL_ITEM_NOTE = (
    "This product covers only a small part of the photo (a watch is ~40px wide in a full-body shot), so its "
    "close-up here is an enlargement of very few pixels. Judge what is actually resolvable at that size: "
    "case/dial/strap COLOURS, shape, proportions and how it is worn. Do NOT mark it down for unreadable text, "
    "numerals, logos, stitching or engraving — a customer cannot see those either, and fine ornament (filigree, "
    "beading, tiny stones) is necessarily simplified at this size. A chain's LINK PATTERN (rope, curb, figaro, "
    "box, franco), its clasp and any hallmark tag are in the same category: a 2mm chain is one or two pixels "
    "wide on a body, so a rope chain cannot look twisted there and drawing it as a plain line of the right "
    "colour and thickness is correct, not wrong. A necklace partly hidden by hair, a collar or a neckline is "
    "normal and is not a fault. Mark it down only if the colours, the overall silhouette/shape or the placement "
    "are wrong, or the item is missing."
)


async def judge(
    product: np.ndarray,
    before: np.ndarray,
    after: np.ndarray,
    region: Region,
    description: str,
    small_item: bool = False,
) -> Verdict:
    before_crop, after_crop = _crop(before, region), _crop(after, region)
    answer = await ask_json(
        _INSTRUCTIONS + ("\n" + _SMALL_ITEM_NOTE if small_item else ""),
        [
            {"type": "text", "text": f"The product: {description}"},
            {"type": "text", "text": "(1) product reference:"},
            image_part(product, 768),
            {"type": "text", "text": "(2) BEFORE, product area:"},
            image_part(before_crop, 768),
            {"type": "text", "text": "(3) AFTER, product area:"},
            image_part(after_crop, 768),
            {"type": "text", "text": "(4) whole AFTER photo:"},
            image_part(after, 1024),
        ],
    )
    issues = [str(i)[:160] for i in (answer.get("issues") or [])][:6] if isinstance(answer.get("issues"), list) else []
    product_match = _num(answer.get("product_match"))

    # Deterministic, product-agnostic hard gates — never asking what the
    # product IS, only whether this crop's own pixels back up the VLM's
    # opinion. A VLM asked to score a single image in isolation can be
    # talked into a generous number by a confident-looking render even
    # when it is the wrong colour or was never drawn at all; neither of
    # these checks can be.
    if not region_was_touched(before_crop, after_crop):
        product_match = 0.0
        issues = ["nothing changed in this item's own region — it was never drawn"] + issues
    else:
        delta_e = color_mismatch(after_crop, product)
        if delta_e is not None and delta_e >= _COLOR_FAIL_DELTA_E:
            product_match = min(product_match, 3.0)
            issues = [f"colour does not match the product photo (ΔE {delta_e:.0f})"] + issues

    return Verdict(
        product_match=product_match,
        worn_correctly=_num(answer.get("worn_correctly")),
        realism=_num(answer.get("realism")),
        issues=issues[:6],
        fix=str(answer.get("fix") or "")[:200],
    )


_EXTRA_ITEMS_INSTRUCTIONS = (
    "You compare a BEFORE and AFTER photo from a virtual try-on. The only fashion or accessory changes in AFTER "
    "should be the exact products listed below being added onto her — nothing else. Reply with JSON only: "
    '{"extra_items": ["short description", ...]}, listing anything visible in AFTER that is NOT in BEFORE and '
    "is NOT one of the listed products — an empty list if there is nothing new. A colour, size or fit difference "
    "in a listed product is not a new item; a garment or accessory of a kind never listed is. Ignore hair, makeup "
    "and skin — judge fashion items and accessories only."
)


async def check_for_extra_items(before: np.ndarray, after: np.ndarray, expected: list[str]) -> list[str]:
    """What Gemini's own "complete the look" habit adds beyond what was
    asked for — a necklace, a second bracelet — that no per-item check
    would ever catch, since every per-item judge only asks "is THIS
    product there", never "is anything else there that shouldn't be".
    Live, on a genuine 5-for-5 pass: a necklace and a second bracelet,
    neither selected, both invented anyway."""
    listed = "\n".join(f"- {d}" for d in expected) or "(none)"
    try:
        answer = await ask_json(
            _EXTRA_ITEMS_INSTRUCTIONS,
            [
                {"type": "text", "text": f"Expected products:\n{listed}"},
                {"type": "text", "text": "BEFORE:"},
                image_part(before, 1024),
                {"type": "text", "text": "AFTER:"},
                image_part(after, 1024),
            ],
        )
    except VisionError:
        return []  # can't confirm a violation without a working check — never fail a render over that
    extras = answer.get("extra_items")
    return [str(e)[:160] for e in extras][:6] if isinstance(extras, list) else []
