"""Report-only quality control for a direct try-on.

Everything here READS the three images and returns numbers. Nothing is
written back, nothing gates the result, and a failure inside QC becomes an
`error` entry in the report — it can never fail or alter a try-on.

What it measures, and what it honestly cannot:

* output resolution — exact.
* face similarity — a Haar-cascade face is found in the person photo, then
  the same fractional region is compared in the result. Needs a frontal face
  in the photo; says so when it can't.
* difference outside the edited region — there is no person segmentation or
  product-category logic in this codebase, so the "edited region" is not
  known in advance. Instead the result is compared with the photo (both at
  working size) and the report gives where things changed (`changed_bbox`),
  plus the change measured in places a product normally does not reach: the
  face, the hair around it, and the left/right/top margins of the frame.
  Treat these as indicators, not proof.
* product-match score — a colour comparison between the product photo and
  the part of the result that changed. It catches a wrong colour or a missing
  product; it cannot see a changed neckline or pattern. The optional VLM
  score (opt-in, paid) is the only check that reads design.
"""

from __future__ import annotations

import asyncio
import io
import json

import cv2
import numpy as np
from PIL import Image

from app.core.logging import logger
from app.services.face_restore import _CASCADE, Box, detect_face  # noqa: F401

WORK_SIDE = 512  # long side of the comparison grids
_CHANGE_THRESHOLD = 0.12  # 0..1 per-pixel colour difference counted as "changed"
_FACE_PAD = 0.15  # context around the detected face when comparing
_HEAD_UP, _HEAD_SIDE = 0.55, 0.28  # hair reaches this far beyond the face box (as in face_restore)
_MARGIN = 0.06  # share of the frame used as the left/right/top control bands

# Flags that mean the product was not verified. A job with any of these is
# held for review and never reported as successfully applied. The rest stay
# advisory (frame_margins_changed: FASHN may legitimately re-frame the photo).
HARD_FLAGS = frozenset(
    {
        "qc_failed",
        "qc_unreadable_image",
        "no_visible_edit",
        "face_changed",
        "low_resolution",
        "alignment_failed",
        "face_check_inconclusive",
        "low_product_colour_match",
    }
)

THRESHOLDS = {
    "min_long_side_px": 1024,
    "min_face_similarity": 0.60,
    "max_border_changed_fraction": 0.08,
    "max_head_changed_fraction": 0.15,
    "min_edit_fraction": 0.005,
    "min_product_match": 0.35,
    "max_aspect_difference": 0.02,
}

Frac = tuple[float, float, float, float]


def _decode(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not a decodable image")
    return img


def _work_size(w: int, h: int) -> tuple[int, int]:
    scale = min(1.0, WORK_SIDE / max(w, h))
    return max(1, round(w * scale)), max(1, round(h * scale))


def _frac_box(box: Box, w: int, h: int) -> Frac:
    return box.x / w, box.y / h, (box.x + box.w) / w, (box.y + box.h) / h


def _px(frac: Frac, w: int, h: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = frac
    return (
        max(0, int(round(x0 * w))),
        max(0, int(round(y0 * h))),
        min(w, int(round(x1 * w))),
        min(h, int(round(y1 * h))),
    )


def _pad(frac: Frac, up: float, side: float, down: float) -> Frac:
    x0, y0, x1, y1 = frac
    bw, bh = x1 - x0, y1 - y0
    return max(0.0, x0 - side * bw), max(0.0, y0 - up * bh), min(1.0, x1 + side * bw), min(1.0, y1 + down * bh)


def _iou(a: Frac, b: Frac) -> float:
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _difference(before: np.ndarray, after: np.ndarray) -> np.ndarray:
    """Per-pixel colour difference, 0..1, on lightly blurred copies so sensor
    noise and re-encoding don't register as change."""
    a = cv2.GaussianBlur(before, (5, 5), 0).astype(np.int16)
    b = cv2.GaussianBlur(after, (5, 5), 0).astype(np.int16)
    return np.abs(a - b).max(axis=2).astype(np.float32) / 255.0


def _changed_fraction(mask: np.ndarray, frac: Frac) -> float | None:
    h, w = mask.shape
    x0, y0, x1, y1 = _px(frac, w, h)
    region = mask[y0:y1, x0:x1]
    return round(float(region.mean()), 4) if region.size else None


def _face_candidates(img: np.ndarray) -> list[Box]:
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    min_side = max(24, min(img.shape[:2]) // 25)
    faces = _CASCADE.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=6, minSize=(min_side, min_side))
    return [Box(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]


# two detections are the same face when their boxes overlap at least this much
_FACE_PAIR_MIN_IOU = 0.3


def _matched_face(person: np.ndarray, result: np.ndarray) -> tuple[Frac, Frac, float] | None:
    """The face found in the SAME place in both images. Live: the detector's
    largest box in a photo was a false hit on a denim top, while the render's
    was the real face; comparing those two regions reported "face changed" on
    a correct render. Only a pair of detections that agree is trusted."""
    ph, pw = person.shape[:2]
    rh, rw = result.shape[:2]
    best: tuple[Frac, Frac, float] | None = None
    for a in _face_candidates(person):
        fa = _frac_box(a, pw, ph)
        for b in _face_candidates(result):
            fb = _frac_box(b, rw, rh)
            iou = _iou(fa, fb)
            if iou >= _FACE_PAIR_MIN_IOU and (best is None or iou > best[2]):
                best = (fa, fb, iou)
    return best


def _skin_tone_shift(person: np.ndarray, result: np.ndarray, frac: Frac) -> dict:
    """How far the skin of the face moved in colour: the middle of the face
    (cheeks, nose, no hair or background) in Lab, original vs result. Report
    only. lightness_shift > 0 means the result is lighter."""
    inner = (frac[0] + (frac[2] - frac[0]) * 0.25, frac[1] + (frac[3] - frac[1]) * 0.35,
             frac[2] - (frac[2] - frac[0]) * 0.25, frac[3] - (frac[3] - frac[1]) * 0.15)
    means = []
    for img in (person, result):
        h, w = img.shape[:2]
        x0, y0, x1, y1 = _px(inner, w, h)
        crop = img[y0:y1, x0:x1]
        if crop.size == 0:
            return {}
        means.append(cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32).mean(axis=0))
    # OpenCV 8-bit Lab: L is 0..255 for 0..100
    shift = means[1] - means[0]
    d_l, d_a, d_b = float(shift[0]) * 100 / 255, float(shift[1]), float(shift[2])
    return {
        "skin_delta_e": round((d_l**2 + d_a**2 + d_b**2) ** 0.5, 2),
        "skin_lightness_shift": round(d_l, 2),
    }


def _face_report(person: np.ndarray, result: np.ndarray, diff_mask: np.ndarray | None) -> dict:
    ph, pw = person.shape[:2]
    rh, rw = result.shape[:2]
    pair = _matched_face(person, result)
    if pair is None:
        found_in_photo, found_in_result = bool(_face_candidates(person)), bool(_face_candidates(result))
        if not found_in_photo and not found_in_result:
            # no face anywhere (a back view, a cropped torso): nothing to compare
            return {"face_found_in_photo": False, "face_found_in_result": False, "face_similarity": None,
                    "note": "no frontal face detected in either image"}
        return {
            "face_found_in_photo": found_in_photo,
            "face_found_in_result": found_in_result,
            "face_similarity": None,
            "inconclusive": True,
            "note": "no face was found in the same place in both images, so identity could not be checked",
        }
    frac, _, iou = pair
    out: dict = {
        "face_found_in_photo": True,
        "face_found_in_result": True,
        "face_box": [round(v, 4) for v in frac],
        "face_box_iou": round(iou, 4),
    }

    padded = _pad(frac, _FACE_PAD, _FACE_PAD, _FACE_PAD)
    crops = []
    for img in (person, result):
        h, w = img.shape[:2]
        x0, y0, x1, y1 = _px(padded, w, h)
        crop = img[y0:y1, x0:x1]
        if crop.size == 0:
            return {**out, "face_similarity": None, "note": "face region is empty"}
        crops.append(cv2.cvtColor(cv2.resize(crop, (96, 96), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY))
    out.update(_skin_tone_shift(person, result, frac))
    a, b = crops
    if float(a.std()) < 1.0 or float(b.std()) < 1.0:
        return {**out, "face_similarity": None, "note": "face region is flat"}
    # zero-mean normalised correlation of the two face crops, -1..1
    ncc = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0][0])
    out["face_similarity"] = round(max(-1.0, min(1.0, ncc)), 4)
    out["face_mean_abs_diff"] = round(float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean() / 255.0), 4)
    if diff_mask is not None:
        out["face_changed_fraction"] = _changed_fraction(diff_mask, frac)
        out["head_changed_fraction"] = _changed_fraction(diff_mask, _pad(frac, _HEAD_UP, _HEAD_SIDE, 0.0))
    return out


def _foreground_pixels(product: np.ndarray) -> np.ndarray:
    """The product's own pixels: everything that isn't the photo's backdrop,
    judged against the colour along the frame's edge. Falls back to the whole
    image when the product fills the frame."""
    h, w = product.shape[:2]
    ww, wh = _work_size(w, h)
    small = cv2.resize(product, (ww, wh), interpolation=cv2.INTER_AREA)
    edge = np.concatenate([small[0], small[-1], small[:, 0], small[:, -1]])
    background = np.median(edge, axis=0)
    far = np.linalg.norm(small.astype(np.float32) - background.astype(np.float32), axis=2) > 28
    pixels = small[far]
    return pixels if pixels.shape[0] >= 0.02 * ww * wh else small.reshape(-1, 3)


def _hs_histogram(bgr_pixels: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [18, 8], [0, 180, 0, 256])
    total = hist.sum()
    return (hist / total if total > 0 else hist).astype(np.float32)


def _mean_lab(bgr_pixels: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr_pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).mean(axis=0)


def _product_report(product: np.ndarray, after: np.ndarray, mask: np.ndarray) -> dict:
    if mask.mean() < THRESHOLDS["min_edit_fraction"]:
        return {"product_match_score": None, "note": "nothing visibly changed, so there is no product region to compare"}
    ys, xs = np.nonzero(mask)
    region = after[ys, xs]  # the changed region's pixels, from the result at working size
    if region.shape[0] < 50:
        return {"product_match_score": None, "note": "changed region too small to compare"}
    product_pixels = _foreground_pixels(product)
    distance = float(cv2.compareHist(_hs_histogram(product_pixels), _hs_histogram(region), cv2.HISTCMP_BHATTACHARYYA))
    delta_e = float(np.linalg.norm(_mean_lab(product_pixels) - _mean_lab(region)))
    return {
        "product_match_score": round(max(0.0, 1.0 - distance), 4),
        "mean_colour_delta_e": round(delta_e, 2),
        "method": "hue/saturation histogram of the product vs the pixels that changed",
    }


def _resolution_report(person_bytes: bytes, result_bytes: bytes) -> dict:
    with Image.open(io.BytesIO(result_bytes)) as out_img, Image.open(io.BytesIO(person_bytes)) as in_img:
        ow, oh = out_img.size
        iw, ih = in_img.size
        fmt = out_img.format
    return {
        "output_width": ow,
        "output_height": oh,
        "output_megapixels": round(ow * oh / 1e6, 2),
        "output_format": fmt,
        "input_width": iw,
        "input_height": ih,
        "scale_vs_input": round(max(ow, oh) / max(iw, ih), 3),
        "aspect_difference": round(abs(ow / oh - iw / ih) / (iw / ih), 4),
    }


# below this median per-pixel difference (0..1), a candidate framing is taken
# to line the photo up with the render: most of a try-on frame (background,
# floor, face) is unchanged, so a correct framing leaves a small median
_ALIGN_MAX_MEDIAN = 0.06


def _align_person(person: np.ndarray, result: np.ndarray) -> tuple[np.ndarray | None, dict]:
    """FASHN returns its own standard frame size (live: a photo came back as
    848x1264), so the photo is reframed to the render's shape before any
    pixel comparison. Each plausible framing is tried and the one that best
    matches the render's unchanged background is used. None when no framing
    lines up, so a misaligned comparison never passes or fails a product."""
    ph, pw = person.shape[:2]
    rh, rw = result.shape[:2]
    target = rw / rh
    candidates: dict[str, np.ndarray] = {"stretch": person}
    if pw / ph > target:  # photo is wider: crop its sides
        cw = max(1, round(ph * target))
        candidates["center_crop"] = person[:, (pw - cw) // 2 : (pw - cw) // 2 + cw]
        candidates["left_crop"] = person[:, :cw]
        candidates["right_crop"] = person[:, pw - cw :]
    else:  # photo is taller: crop top/bottom
        ch = max(1, round(pw / target))
        candidates["center_crop"] = person[(ph - ch) // 2 : (ph - ch) // 2 + ch, :]
        candidates["top_crop"] = person[:ch, :]
        candidates["bottom_crop"] = person[ph - ch :, :]

    small = (max(1, round(128 * target)), 128) if target < 1 else (128, max(1, round(128 / target)))
    reference = cv2.resize(result, small, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    scores = {}
    for name, img in candidates.items():
        trial = cv2.resize(img, small, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        scores[name] = float(np.median(np.abs(trial - reference).mean(axis=2)))
    best = min(scores, key=scores.get)
    info = {"method": best, "median_difference": round(scores[best], 4), "tried": {k: round(v, 4) for k, v in scores.items()}}
    if scores[best] > _ALIGN_MAX_MEDIAN:
        return None, info
    return cv2.resize(candidates[best], (rw, rh), interpolation=cv2.INTER_AREA), info


def _difference_report(person: np.ndarray, result: np.ndarray) -> tuple[dict, np.ndarray, np.ndarray, list[str]]:
    ph, pw = person.shape[:2]
    ww, wh = _work_size(pw, ph)
    before = cv2.resize(person, (ww, wh), interpolation=cv2.INTER_AREA)
    after = cv2.resize(result, (ww, wh), interpolation=cv2.INTER_AREA)
    raw = (_difference(before, after) > _CHANGE_THRESHOLD).astype(np.uint8)
    mask = cv2.morphologyEx(raw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    ys, xs = np.nonzero(mask)
    margins = np.concatenate(
        [
            mask[:, : int(ww * _MARGIN)].ravel(),
            mask[:, ww - int(ww * _MARGIN) :].ravel(),
            mask[: int(wh * _MARGIN), :].ravel(),
        ]
    )
    report = {
        "compared_at": [ww, wh],
        "edited_fraction": round(float(mask.mean()), 4),
        "changed_bbox": (
            [round(xs.min() / ww, 4), round(ys.min() / wh, 4), round((xs.max() + 1) / ww, 4), round((ys.max() + 1) / wh, 4)]
            if xs.size
            else None
        ),
        "border_changed_fraction": round(float(margins.mean()), 4),
        "note": "indicative: no segmentation exists, so 'outside the edit' is judged on the face, hair and frame margins",
    }
    flags = []
    if report["edited_fraction"] < THRESHOLDS["min_edit_fraction"]:
        flags.append("no_visible_edit")
    if report["border_changed_fraction"] > THRESHOLDS["max_border_changed_fraction"]:
        flags.append("frame_margins_changed")
    return report, mask, after, flags


def measure(person_bytes: bytes, product_bytes: bytes, result_bytes: bytes) -> dict:
    """The numeric checks. Pure and synchronous: CPU only, no network."""
    report: dict = {"report_only": True, "thresholds": THRESHOLDS}
    flags: list[str] = []
    try:
        report["resolution"] = _resolution_report(person_bytes, result_bytes)
        person, result, product = _decode(person_bytes), _decode(result_bytes), _decode(product_bytes)
    except Exception as exc:  # noqa: BLE001 — QC never fails a try-on
        report["error"] = f"could not read an image: {str(exc)[:160]}"
        report["flags"] = ["qc_unreadable_image"]
        return report

    res = report["resolution"]
    if max(res["output_width"], res["output_height"]) < THRESHOLDS["min_long_side_px"]:
        flags.append("low_resolution")
    aspect_ok = res["aspect_difference"] <= THRESHOLDS["max_aspect_difference"]
    if not aspect_ok:
        aligned, report["alignment"] = _align_person(person, result)
        if aligned is None:
            flags.append("alignment_failed")
        else:
            person = aligned
            aspect_ok = True
            flags.append("aspect_ratio_changed")  # advisory: FASHN's own frame size, lined up before comparing

    mask: np.ndarray | None = None
    after_work: np.ndarray | None = None
    if aspect_ok:
        try:
            report["difference"], mask, after_work, extra = _difference_report(person, result)
            flags += extra
        except Exception as exc:  # noqa: BLE001
            report["difference"] = {"error": str(exc)[:200]}
            mask = after_work = None
    else:
        report["difference"] = {"skipped": "the photo could not be lined up with the render, so a pixel comparison would be meaningless"}

    try:
        report["face"] = _face_report(person, result, mask)
        similarity = report["face"].get("face_similarity")
        if report["face"].get("inconclusive"):
            flags.append("face_check_inconclusive")
        elif similarity is not None and similarity < THRESHOLDS["min_face_similarity"]:
            flags.append("face_changed")
        head = report["face"].get("head_changed_fraction")
        if head is not None and head > THRESHOLDS["max_head_changed_fraction"]:
            flags.append("head_changed")
    except Exception as exc:  # noqa: BLE001
        report["face"] = {"error": str(exc)[:200]}

    try:
        if mask is not None and after_work is not None:
            report["product"] = _product_report(product, after_work, mask)
            score = report["product"].get("product_match_score")
            if score is not None and score < THRESHOLDS["min_product_match"]:
                flags.append("low_product_colour_match")
        else:
            report["product"] = {"product_match_score": None, "note": "needs the pixel comparison"}
    except Exception as exc:  # noqa: BLE001
        report["product"] = {"error": str(exc)[:200]}

    report["flags"] = flags
    return report


async def _vlm_report(product: np.ndarray, person: np.ndarray, result: np.ndarray, name: str, url: str) -> dict:
    """The existing OpenAI vision inspector, asked for a score only. A paid
    call: run_qc invokes it only when TRYON_DIRECT_VLM_QC is on."""
    from app.services.tryon_quality.compose import Region
    from app.services.tryon_quality.judge import judge

    verdict = await judge(product, person, result, Region(0.0, 0.0, 1.0, 1.0), name, False, url)
    return {
        "enabled": True,
        "product_match": verdict.product_match,
        "worn_correctly": verdict.worn_correctly,
        "realism": verdict.realism,
        "issues": verdict.issues,
        "scale": "0-10",
    }


async def run_qc(
    person_bytes: bytes,
    product_bytes: bytes,
    result_bytes: bytes,
    *,
    product_name: str = "",
    product_url: str = "",
    with_vlm: bool = False,
) -> dict:
    """The full report. Never raises, never touches the images."""
    try:
        report = await asyncio.to_thread(measure, person_bytes, product_bytes, result_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("tryon_direct_qc_failed", error=str(exc)[:200])
        return {"report_only": True, "error": str(exc)[:200], "flags": ["qc_failed"]}

    report["vlm"] = {"enabled": False}
    if with_vlm:
        try:
            report["vlm"] = await _vlm_report(
                _decode(product_bytes), _decode(person_bytes), _decode(result_bytes), product_name or "the product", product_url
            )
        except Exception as exc:  # noqa: BLE001 — a paid, optional signal must never affect the job
            logger.warning("tryon_direct_vlm_failed", error=str(exc)[:200])
            report["vlm"] = {"enabled": True, "error": str(exc)[:200]}
    try:
        json.dumps(report)  # fail here, in QC, rather than when the row is written
    except (TypeError, ValueError) as exc:
        return {"report_only": True, "error": f"report not serialisable: {exc}", "flags": ["qc_failed"]}
    return report


def qc_gate(report: dict) -> dict:
    """Whether the render may be delivered as a verified product application.

    Passes only when no hard check failed. Every failed check is recorded by
    name, so a held job says exactly what did not verify."""
    flags = list(report.get("flags") or [])
    failed = [flag for flag in flags if flag in HARD_FLAGS]
    if not failed and report.get("error") and not report.get("flags"):
        failed = ["qc_failed"]
    return {
        "passed": not failed,
        "failed_checks": failed,
        "advisory": [flag for flag in flags if flag not in HARD_FLAGS],
    }
