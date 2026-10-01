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

from app.core.logging import logger
from app.services.tryon_quality.compose import Region
from app.services.tryon_quality.cutout import product_cutout_mask
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


def _dominant_lab(img: np.ndarray, mask: np.ndarray | None = None) -> tuple[float, float, float]:
    """The median L*a*b* of `img`'s pixels where `mask` (0..255) is
    foreground, or of every pixel when no mask is given.

    An earlier version of this function tried to guess the backdrop by
    brightness and saturation alone ("bright and near-neutral = studio
    wall") — it silently excluded white, cream, silver and light-grey
    PRODUCTS too, since they look exactly like a bright neutral backdrop
    by that same measure. There is no way to tell a white product from a
    white wall by colour statistics alone; a real foreground mask
    (product_cutout_mask, a real background-removal model) is the only
    thing that works for a product of any colour. No mask is needed for
    a result crop that is already cropped to the item's own region —
    every pixel there is already "inside the mask"."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    if mask is None:
        keep = np.ones(img.shape[:2], dtype=bool)
    else:
        keep = mask > 127
        if keep.sum() < 50:
            keep = np.ones(img.shape[:2], dtype=bool)
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


def color_mismatch(result_crop: np.ndarray, product: np.ndarray, product_image_url: str) -> float:
    """How far the result's own dominant colour is from the product
    photo's, as a perceptual CIEDE2000 distance (never asks what kind of
    product this is).

    The product side uses a real foreground cutout (product_cutout_mask,
    cached forever per product image) so the backdrop never pollutes the
    estimate, whatever colour the product itself is — including a white
    product on a white backdrop. The result side uses every pixel in
    `result_crop` unmasked: it's already cropped to the item's own
    region, so every pixel in it already counts as "inside the mask"."""
    product_mask = product_cutout_mask(product, product_image_url)
    return _delta_e_ciede2000(_dominant_lab(result_crop), _dominant_lab(product, product_mask))


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


def _gradient_magnitude(img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    mag = np.zeros(img.shape[:2], np.float32)
    for c in range(3):
        gx = cv2.Sobel(lab[..., c], cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(lab[..., c], cv2.CV_32F, 0, 1, ksize=3)
        mag += gx * gx + gy * gy
    return np.sqrt(mag)


def _band_kernel(radius: int) -> np.ndarray:
    size = 2 * radius + 1
    return cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))


def seam_score(image: np.ndarray, region: Region, band: int = 2) -> float:
    """How much more a thin ring straddling the pasted region's own
    rectangle boundary stands out, in local edge strength, than the
    pixels immediately inside and immediately outside it.

    A hard paste — a straight rectangle cut, or a feather too narrow to
    hide a colour/lighting mismatch — leaves a ring of elevated local
    contrast that traces the paste boundary exactly, on all four sides,
    regardless of what the product is. A garment's own real edge (a hem,
    a collar, a sleeve cuff) creates local contrast too, but not one that
    happens to coincide with this box's own rectangle; comparing the
    boundary ring to the bands just inside and just outside it (not to
    the image as a whole, which has its own unrelated texture) is what
    makes this product-agnostic: it never asks what kind of edge this is,
    only whether an edge exists exactly where a paste would leave one.

    Never asked what the product is, so it's as valid for a watch as a
    gown. Returns 0.0 when the box reaches the photo's own edge — there's
    no "outside" band left to compare against on that side."""
    h, w = image.shape[:2]
    x0, y0, x1, y1 = region.pixels(w, h)
    margin = band * 3
    if x0 < margin or y0 < margin or x1 > w - margin or y1 > h - margin or x1 - x0 <= margin * 2 or y1 - y0 <= margin * 2:
        return 0.0
    rect = np.zeros((h, w), np.uint8)
    rect[y0:y1, x0:x1] = 1
    k1, k2 = _band_kernel(band), _band_kernel(band * 2)
    dilated1, eroded1 = cv2.dilate(rect, k1), cv2.erode(rect, k1)
    dilated2, eroded2 = cv2.dilate(rect, k2), cv2.erode(rect, k2)
    boundary = (dilated1 > 0) & (eroded1 == 0)
    inner_ring = (eroded1 > 0) & (eroded2 == 0)
    outer_ring = (dilated2 > 0) & (dilated1 == 0)
    mag = _gradient_magnitude(image)
    # The boundary ring is a few pixels wide so it reliably straddles the
    # true edge, but that means most of its own pixels still sit a little
    # off that edge, in flat territory either side of it — a median over
    # the whole ring is dominated by those, not by the edge itself. A high
    # percentile picks out the ring's own sharpest pixels, which is what a
    # hard paste's edge actually looks like; the baseline bands have no
    # edge to find in the first place, so their median is the right,
    # noise-robust read of their ordinary local texture.
    boundary_level = float(np.percentile(mag[boundary], 90)) if boundary.any() else 0.0
    baseline = max(
        float(np.median(mag[inner_ring])) if inner_ring.any() else 0.0,
        float(np.median(mag[outer_ring])) if outer_ring.any() else 0.0,
        1e-6,
    )
    return boundary_level / baseline


# Shadow mode, like distractor ranking: logged on every judge() call so a
# real threshold can be calibrated from actual passing and failing renders
# once enough of them exist, not guessed at from synthetic tests alone.
# Not yet wired to fail anything.
_SEAM_RATIO_WORTH_LOGGING = 2.0


def has_seam(image: np.ndarray, region: Region, band: int = 4, threshold: float = 2.5) -> bool:
    return seam_score(image, region, band) >= threshold


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
    small_item: bool,
    product_image_url: str,
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
        delta_e = color_mismatch(after_crop, product, product_image_url)
        if delta_e >= _COLOR_FAIL_DELTA_E:
            product_match = min(product_match, 3.0)
            issues = [f"colour does not match the product photo (ΔE {delta_e:.0f})"] + issues

    # Shadow mode: logged only, not yet a failure — see has_seam()'s own
    # docstring and _SEAM_RATIO_WORTH_LOGGING. Calibrate a real fail
    # threshold once enough real seam/clean pairs exist; a synthetic test
    # can prove the signal fires on an obvious hard paste, not what ratio
    # a genuine one comes back at.
    seam = seam_score(after, region)
    if seam >= _SEAM_RATIO_WORTH_LOGGING:
        logger.info("tryon_seam_signal", region=str(region), seam_score=round(seam, 2))

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
