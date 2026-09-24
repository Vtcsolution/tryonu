"""Keep the person; take only the product from the render.

Why this exists (measured on real FASHN tryon-max renders): the model
regenerates the WHOLE frame, not just the product — the face, skin tone,
beard, hair, background and carpet texture all come back redrawn (face
region off by 13.8-19.3 grey levels on average), and in a multi-item
outfit each step re-fed the previous render, so the drift compounded.
Prompts can't stop that. So after every render we:

1. align the render to the input photo (it comes back ~1.65x larger with a
   very slightly different framing),
2. undo its global colour/contrast shift, fitted on pixels that should not
   have changed,
3. undo its LOCAL lighting drift too (it relights walls and skin a few
   shades differently in places),
4. split what's left into changed areas; the strong changes are the
   product (plus any body part the model moved to wear it — it re-poses a
   hand under a watch); faint changes (re-textured jeans or carpet) are
   only taken right next to it, fading out so no edge shows; the face is
   never taken unless the item is worn on the head,
5. paste only that onto the input.

Everything else is the person's original pixels (face region: 0.00 change).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class Region:
    """A box as fractions of the image (0..1)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def pixels(self, w: int, h: int, pad: float = 0.0) -> tuple[int, int, int, int]:
        bw, bh = (self.x1 - self.x0) * w, (self.y1 - self.y0) * h
        return (
            max(0, int(self.x0 * w - pad * bw)),
            max(0, int(self.y0 * h - pad * bh)),
            min(w, int(self.x1 * w + pad * bw)),
            min(h, int(self.y1 * h + pad * bh)),
        )


def decode(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image")
    return img


def encode_jpeg(img: np.ndarray, quality: int = 94) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("could not encode image")
    return buf.tobytes()


def align(render: np.ndarray, base: np.ndarray) -> tuple[np.ndarray, float]:
    """The render warped onto the base's pixel grid, and how well they line
    up (0..1, share of feature matches consistent with the transform).
    Renders come back larger and with a slightly different aspect, so a plain
    resize is off by a few pixels — enough to ghost edges when compositing."""
    h, w = base.shape[:2]
    resized = cv2.resize(render, (w, h), interpolation=cv2.INTER_AREA)

    orb = cv2.ORB_create(4000)
    g1 = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    k1, d1 = orb.detectAndCompute(g1, None)
    k2, d2 = orb.detectAndCompute(g2, None)
    if d1 is None or d2 is None or len(k1) < 30 or len(k2) < 30:
        return resized, 0.0
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2)
    if len(matches) < 30:
        return resized, 0.0
    src = np.float32([k1[m.queryIdx].pt for m in matches])
    dst = np.float32([k2[m.trainIdx].pt for m in matches])
    matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if matrix is None:
        return resized, 0.0
    scale = float(np.hypot(matrix[0, 0], matrix[1, 0]))
    shift = float(np.hypot(matrix[0, 2], matrix[1, 2]))
    if not 0.9 < scale < 1.1 or shift > 0.08 * max(w, h):
        return resized, 0.0  # implausible — the render isn't a re-framing of the same photo
    warped = cv2.warpAffine(resized, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return warped, float(inliers.sum()) / len(matches)


def _lab_diff(a: np.ndarray, b: np.ndarray, blur: float = 1.5) -> np.ndarray:
    la = cv2.cvtColor(cv2.GaussianBlur(a, (0, 0), blur), cv2.COLOR_BGR2LAB).astype(np.float32)
    lb = cv2.cvtColor(cv2.GaussianBlur(b, (0, 0), blur), cv2.COLOR_BGR2LAB).astype(np.float32)
    return np.linalg.norm(la - lb, axis=2)


def match_colors(render: np.ndarray, base: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """Undo the render's global colour/contrast drift: fit, per channel, the
    straight line mapping render -> base over pixels that should be
    identical (`keep` = outside the product region), and apply it."""
    out = render.astype(np.float32)
    sel = keep.astype(bool)
    if sel.sum() < 500:
        return render
    step = max(1, int(sel.sum() // 200_000))  # a subsample is plenty for 2 numbers per channel
    for c in range(3):
        x = out[..., c][sel][::step]
        y = base[..., c][sel][::step].astype(np.float32)
        if x.std() < 2:
            continue
        a, b = _line(x, y)
        # refit without pixels that genuinely changed (the model redrew
        # something there) — they'd drag the correction off
        residual = np.abs(x * a + b - y)
        close = residual < max(4.0, 2 * float(np.median(residual)))
        if close.sum() > 100:
            a, b = _line(x[close], y[close])
        if 0.6 < a < 1.6:  # a sane correction, not a fit to garbage
            out[..., c] = out[..., c] * a + b
    return np.clip(out, 0, 255).astype(np.uint8)


def match_local_tone(render: np.ndarray, base: np.ndarray, agree_below: float = 16.0, passes: int = 1) -> np.ndarray:
    """Undo the render's LOCAL lighting drift. FASHN relights the whole frame
    slightly differently (a wall a few shades lighter here, darker there);
    after the global fit that residue still reads as "changed", so a merge
    took patches of FASHN's wall and their edges showed. Estimate a smooth
    offset field from pixels where the two images agree (the product areas
    differ a lot and are ignored) and remove it."""
    # Kept mild on purpose (tested): allowing larger shifts to count as
    # "lighting" also explained away real products — khaki chinos over blue
    # jeans came out with blue patches, a black shirt went grey-green. A
    # lighting correction can't tell a recoloured garment from relighting,
    # so it only touches areas that already nearly match (walls, skin).
    for _ in range(passes):
        render = _local_tone_pass(render, base, agree_below)
    return render


def _local_tone_pass(render: np.ndarray, base: np.ndarray, agree_below: float) -> np.ndarray:
    h, w = base.shape[:2]
    small = 512 / max(h, w)  # the field is smooth: compute it small, apply it big
    size = (max(1, int(w * small)), max(1, int(h * small)))
    b = cv2.resize(base, size, interpolation=cv2.INTER_AREA).astype(np.float32)
    r = cv2.resize(render, size, interpolation=cv2.INTER_AREA).astype(np.float32)
    agree = (_lab_diff(b.astype(np.uint8), r.astype(np.uint8), blur=1.0) < agree_below).astype(np.float32)
    if agree.mean() < 0.2:
        return render  # too little common ground to estimate lighting from
    sigma = 0.035 * max(size)
    weight = cv2.GaussianBlur(agree, (0, 0), sigma)
    offset = np.dstack(
        [cv2.GaussianBlur((b[..., c] - r[..., c]) * agree, (0, 0), sigma) / np.maximum(weight, 0.05) for c in range(3)]
    )
    # only where there's real evidence nearby: deep inside a product area
    # (a new shirt) nothing agrees, and an extrapolated correction would
    # tint the product itself — leave those pixels exactly as rendered
    offset *= np.clip((weight - 0.15) / 0.35, 0, 1)[..., None]
    offset = cv2.resize(offset, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(render.astype(np.float32) + offset, 0, 255).astype(np.uint8)


def _line(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    xm, ym = float(x.mean()), float(y.mean())
    a = float(((x - xm) * (y - ym)).sum() / max(1e-6, ((x - xm) ** 2).sum()))
    return a, ym - a * xm


def _blocked(shape: tuple[int, int], protect: list[tuple[int, int, int, int]]) -> np.ndarray:
    blocked = np.zeros(shape, bool)
    for px0, py0, px1, py1 in protect:
        blocked[max(0, py0) : py1, max(0, px0) : px1] = True
    return blocked


def _changed_areas(diff: np.ndarray, blocked: np.ndarray, low: float) -> tuple[int, np.ndarray]:
    """Connected areas where the render differs from the photo."""
    weak = ((diff > low) & ~blocked).astype(np.uint8)
    # thin slivers are edges the model nudged by a pixel or two (a jeans
    # seam, the skirting board) — not the product; drop them so areas don't
    # connect along them
    weak = cv2.morphologyEx(weak, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    weak = cv2.morphologyEx(weak, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    return cv2.connectedComponents(weak, connectivity=8)


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    solid = np.zeros_like(mask)
    cv2.drawContours(solid, contours, -1, 1, -1)
    return solid


def _strong_cores(
    diff: np.ndarray, blocked: np.ndarray, high: float, min_share: float = 0.0003
) -> tuple[int, np.ndarray, np.ndarray]:
    """Separate blobs of strong change — the product, and separately anything
    else the model changed a lot (re-washed jeans, a patch of re-textured
    carpet). Tiny specks dropped. (count, labels, stats)"""
    h, w = diff.shape
    strong = ((diff > high) & ~blocked).astype(np.uint8)
    strong = cv2.morphologyEx(strong, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    strong = cv2.morphologyEx(strong, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(strong, 8)
    small = stats[:, cv2.CC_STAT_AREA] < max(40, min_share * h * w)
    small[0] = True
    labels[small[labels]] = 0
    return n, labels, stats


def _mask_from(
    core: np.ndarray,
    weak_labels: np.ndarray,
    blocked: np.ndarray,
    reach_share: float = 0.03,
    diff: np.ndarray | None = None,
    high: float = 32.0,
) -> np.ndarray:
    """What to take: the chosen strong blobs (holes filled — a watch face
    that matches the old skin tone), plus faint changes touching them — the
    body part moved to wear the product, the edge of a new hem — but only
    close to the product, fading out so no edge shows. Faint re-texturing
    further away (jeans under a new shirt, the carpet) stays the person's."""
    h, w = core.shape
    core = _fill_holes(core.astype(np.uint8))
    if not core.any():
        return np.zeros((h, w), np.float32)
    touching = np.unique(weak_labels[core.astype(bool) & (weak_labels > 0)])
    taken = (np.isin(weak_labels, touching) | core.astype(bool)).astype(np.uint8)

    reach = reach_share * max(h, w)
    distance = cv2.distanceTransform((1 - core).astype(np.uint8), cv2.DIST_L2, 5)
    fade = np.clip(1.0 - (distance - 0.35 * reach) / (0.65 * reach), 0.0, 1.0).astype(np.float32)
    if diff is not None:
        # Never half-blend two things that disagree strongly: a hand the
        # model moved by a few pixels, blended at 50%, shows as a ghost hand
        # beside the real one (seen live with gpt-image-2 under a watch).
        # Strongly-different pixels connected to the product are taken
        # whole, out to a hand's length; the fade only crosses pixels where
        # the two images nearly agree, where blending is invisible.
        hard_reach = max(reach, 0.08 * max(h, w))
        hard = (taken.astype(bool) & (diff > high) & (distance < hard_reach)).astype(np.uint8)
        hard = cv2.morphologyEx(hard, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
        # ...and grow along any strongly-different pixels touching it, thin
        # ones included: the old hand's 2px outline beside the moved hand was
        # dropped as a "sliver" and stayed visible as a skin-coloured line.
        # Only within a hand's length of the product, though: the growth
        # follows an edge, and the redrawn outline of an arm let a ring pull
        # a 300px strip of forearm into the merge (live: a pale smudge).
        differs = ((diff > 24) & ~blocked & (distance < hard_reach)).astype(np.uint8)
        grow_kernel = np.ones((5, 5), np.uint8)
        for _ in range(max(4, int(0.012 * max(h, w) / 2))):
            hard = cv2.dilate(hard, grow_kernel) & differs | hard
        fade = np.maximum(fade, _fill_holes(hard).astype(np.float32))
        taken = taken | hard

    solid = cv2.dilate(_fill_holes(taken), np.ones((5, 5), np.uint8)).astype(np.float32)
    solid[blocked] = 0
    soft = cv2.GaussianBlur(solid, (0, 0), 2.0) * fade
    soft[blocked] = 0  # the soft edge must not bleed into a protected face
    return soft


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    solid = np.zeros_like(mask)
    cv2.drawContours(solid, contours, -1, 1, -1)
    return solid


def change_mask(
    diff: np.ndarray,
    region: Region | list[Region],
    protect: list[tuple[int, int, int, int]] = (),
    *,
    low: float = 14.0,
    high: float = 32.0,
) -> np.ndarray:
    """Float mask (0..1) of what to take from the render, seeded by rough
    item boxes: the strong-change blobs inside the boxes, grown a short way
    into faint changes around them. Protected boxes (the face, unless the
    item is worn on the head) are never taken."""
    h, w = diff.shape
    blocked = _blocked((h, w), protect)
    _, weak = _changed_areas(diff, blocked, low)
    _, cores, _ = _strong_cores(diff, blocked, high)
    inside = np.zeros((h, w), bool)
    for r in region if isinstance(region, list) else [region]:
        x0, y0, x1, y1 = r.pixels(w, h, 0.15)
        inside[y0:y1, x0:x1] = True
    chosen = np.unique(cores[inside & (cores > 0)])
    return _mask_from(np.isin(cores, chosen) & (cores > 0), weak, blocked, diff=diff, high=high)


def composite(base: np.ndarray, render: np.ndarray, mask: np.ndarray) -> np.ndarray:
    m = mask[..., None]
    return (render.astype(np.float32) * m + base.astype(np.float32) * (1 - m)).astype(np.uint8)


def product_mask(before: np.ndarray, after: np.ndarray, threshold: float = 16.0) -> np.ndarray:
    """Which pixels the renders ended up supplying: everywhere the result
    differs from the photo it started as. The merge only ever takes the
    product and what moved to wear it, so this is exactly that area —
    without having to thread every item's mask through the pipeline."""
    mask = (_lab_diff(before, after) > threshold).astype(np.float32)
    return np.clip(cv2.GaussianBlur(mask, (0, 0), 2.0), 0, 1)


def sharpen_product(image: np.ndarray, mask: np.ndarray, amount: float = 0.55) -> np.ndarray:
    """Put back the crispness the product loses on the way in.

    The person's own pixels are their photo's, at its own resolution. The
    product's pixels come from a render that is at most 1024x1536, and
    they are scaled up to sit on a larger photo — so the garment reads
    softer than the face beside it, which is what a customer sees as "a
    blurry try-on". An unsharp mask restricted to the product area
    narrows that gap.

    Deliberately mild: enough to recover edge definition, not enough to
    ring. Nothing outside the mask is touched, so the face, hair and
    background remain untouched photograph."""
    if amount <= 0 or not mask.any():
        return image
    blurred = cv2.GaussianBlur(image, (0, 0), 1.2)
    sharper = cv2.addWeighted(image.astype(np.float32), 1 + amount, blurred.astype(np.float32), -amount, 0)
    m = np.clip(mask, 0, 1)[..., None]
    out = sharper * m + image.astype(np.float32) * (1 - m)
    return np.clip(out, 0, 255).astype(np.uint8)


@dataclass(frozen=True, slots=True)
class Merge:
    image: np.ndarray
    alignment: float  # 0..1, feature agreement between render and photo
    changed_share: float  # share of the image taken from the render
    mask: np.ndarray


def merge_product(
    base: np.ndarray,
    render: np.ndarray,
    region: Region | list[Region],
    protect: list[tuple[int, int, int, int]] = (),
) -> Merge:
    """The base photo with only the product(s) — found via rough boxes — and
    any body part moved to wear them, taken from the render."""
    aligned, alignment = align(render, base)
    h, w = base.shape[:2]
    keep = np.ones((h, w), np.uint8)
    for r in region if isinstance(region, list) else [region]:
        x0, y0, x1, y1 = r.pixels(w, h, 0.5)
        keep[y0:y1, x0:x1] = 0
    corrected = match_colors(aligned, base, keep)
    mask = change_mask(_lab_diff(base, match_local_tone(corrected, base)), region, protect)
    corrected = match_local_tone(corrected, base, agree_below=16.0, passes=1)
    return Merge(composite(base, corrected, mask), alignment, float(mask.mean()), mask)


# --- the pipeline's path: pixel-exact candidate areas, chosen by vision -----


@dataclass(frozen=True, slots=True)
class Candidate:
    number: int  # the label drawn on the image shown to the vision model
    region: Region  # its exact box
    share: float  # of the image


@dataclass(slots=True)
class Changes:
    """A render prepared for merging: aligned, colour-corrected, and split
    into separate blobs of strong change (candidates)."""

    base: np.ndarray
    aligned: np.ndarray  # the render on the photo's pixel grid, colours as rendered
    render: np.ndarray  # colour-corrected on the whole image — for showing and detecting
    cores: np.ndarray  # strong-change blob labels
    weak: np.ndarray  # faint-change area labels
    blocked: np.ndarray
    diff: np.ndarray
    candidates: list[Candidate]
    _label_of: dict[int, int]

    def share_of(self, numbers: list[int]) -> float:
        return sum(c.share for c in self.candidates if c.number in numbers)

    def refine(self, numbers: list[int], high: float = 60.0) -> "Changes":
        """Split the chosen areas again at a higher strength. An image model
        that redraws a lot (OpenAI re-renders the T-shirt hem and hands) can
        fold a watch into one big changed area with them; at a higher
        threshold the steel-and-blue watch stands apart from redrawn fabric."""
        chosen = [self._label_of[n] for n in numbers if n in self._label_of]
        inside = np.isin(self.cores, chosen) & (self.cores > 0)
        inside = cv2.dilate(inside.astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
        n, cores, stats = _strong_cores(np.where(inside, self.diff, 0), self.blocked, high)
        candidates, label_of = _numbered(cores, stats, n)
        return Changes(self.base, self.aligned, self.render, cores, self.weak, self.blocked, self.diff, candidates, label_of)

    def merge(self, numbers: list[int], reach_share: float = 0.03) -> Merge:
        chosen = [self._label_of[n] for n in numbers if n in self._label_of]
        core = np.isin(self.cores, chosen) & (self.cores > 0) if chosen else np.zeros(self.cores.shape, bool)
        mask = _mask_from(core, self.weak, self.blocked, reach_share, self.diff)
        # colour-fit the pasted pixels on everything EXCEPT the product (and
        # a margin): a big black shirt in the fit dragged it grey-green
        h, w = mask.shape
        keep = (cv2.dilate((mask > 0.02).astype(np.uint8), np.ones((31, 31), np.uint8)) == 0).astype(np.uint8)
        paste = match_local_tone(match_colors(self.aligned, self.base, keep), self.base)
        return Merge(composite(self.base, paste, mask), 1.0, float(mask.mean()), mask)


def find_changes(
    base: np.ndarray,
    render: np.ndarray,
    protect: list[tuple[int, int, int, int]] = (),
    *,
    low: float = 14.0,
    high: float = 32.0,
    max_candidates: int = 12,
    min_share: float = 0.0003,
) -> Changes:
    """Every sizeable blob where the render changed the photo strongly —
    exact boxes from the pixels, which are reliable. Which blobs are the
    product is left to the vision model, which is good at choosing between
    labelled options and poor at giving coordinates."""
    aligned, _ = align(render, base)
    h, w = base.shape[:2]
    # no product box yet: fit on everything; the robust refit drops the
    # pixels the product changed
    # colour fit for FINDING changes only; the pasted pixels get their own
    # fit once the product is chosen (Changes.merge), excluding the product
    corrected = match_local_tone(match_colors(aligned, base, np.ones((h, w), np.uint8)), base)
    diff = _lab_diff(base, corrected)
    blocked = _blocked((h, w), protect)
    _, weak = _changed_areas(diff, blocked, low)
    n, cores, stats = _strong_cores(diff, blocked, high, min_share)
    candidates, label_of = _numbered(cores, stats, n, max_candidates)
    return Changes(base, aligned, corrected, cores, weak, blocked, diff, candidates, label_of)


def _numbered(
    cores: np.ndarray, stats: np.ndarray, n: int, max_candidates: int = 12
) -> tuple[list[Candidate], dict[int, int]]:
    """Number the blobs, biggest first, with their exact boxes."""
    h, w = cores.shape
    present = set(np.unique(cores).tolist()) - {0}
    found = []
    for label in range(1, n):
        if label not in present:
            continue  # dropped as a speck
        x, y, bw, bh = (int(v) for v in stats[label, :4])
        found.append((int(stats[label, cv2.CC_STAT_AREA]), label, Region(x / w, y / h, (x + bw) / w, (y + bh) / h)))
    found.sort(key=lambda f: -f[0])
    candidates, label_of = [], {}
    for number, (area, label, region) in enumerate(found[:max_candidates], start=1):
        candidates.append(Candidate(number, region, area / (h * w)))
        label_of[number] = label
    return candidates, label_of


def draw_candidates(render: np.ndarray, candidates: list[Candidate], max_side: int = 1400) -> np.ndarray:
    """The render with each candidate area boxed and numbered, for the
    vision model to choose from."""
    h, w = render.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    img = cv2.resize(render, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else render.copy()
    ih, iw = img.shape[:2]
    thickness = max(2, iw // 400)
    size = 0.6 + iw / 1800
    boxes = [(c, c.region.pixels(iw, ih)) for c in candidates]
    for _, (x0, y0, x1, y1) in boxes:
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 255), thickness)
    # labels last, each placed where it doesn't cover another label — two
    # boxes sharing a corner once hid "1" under "11" and the wrong box won
    placed: list[tuple[int, int, int, int]] = []
    for c, (x0, y0, x1, y1) in boxes:
        label = str(c.number)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, size, thickness)
        lw, lh = tw + 8, th + 8
        spots = [(x0, y0 - lh), (x0, y0), (x1 - lw, y0 - lh), (x1 - lw, y0), (x0, y1 - lh), (x1 - lw, y1 - lh), (x0, y1)]
        spot = spots[0]
        for sx, sy in spots:
            sx, sy = max(0, min(iw - lw, sx)), max(0, min(ih - lh, sy))
            if all(sx + lw <= px or px + pw <= sx or sy + lh <= py or py + ph <= sy for px, py, pw, ph in placed):
                spot = (sx, sy)
                break
        sx, sy = max(0, min(iw - lw, spot[0])), max(0, min(ih - lh, spot[1]))
        placed.append((sx, sy, lw, lh))
        cv2.rectangle(img, (sx, sy), (sx + lw, sy + lh), (0, 0, 255), -1)
        cv2.putText(img, label, (sx + 4, sy + th + 4), cv2.FONT_HERSHEY_SIMPLEX, size, (255, 255, 255), thickness)
    return img
