"""Image embeddings for shadow-mode distractor ranking (see
distractor_rank.py): OpenAI's CLIP ViT-B/32 vision encoder (MIT —
github.com/openai/CLIP), run directly via ONNX Runtime on CPU, no paid
API call per embedding.

The ONNX export used is Xenova/clip-vit-base-patch32 on Hugging Face — a
straight weight conversion of openai/clip-vit-base-patch32 (same
base_model, no retraining) packaged for Transformers.js; the weights are
still OpenAI's own MIT-licensed CLIP, not a separately licensed model.
The int8-quantized vision-only export (~89MB, downloaded once and cached
under data/clip/, never at import time) is used rather than the ~600MB
full fp32 model or the combined text+vision export: only image
embeddings are needed here, and quantized CPU inference is the point —
not NOT ORB, and not a paid call.

Preprocessing matches openai/clip-vit-base-patch32's own
preprocessor_config.json exactly (resize shortest side to 224 with
bicubic resampling, centre-crop 224x224, normalize with CLIP's own
published per-channel mean/std) — any deviation here would silently
change what the model sees relative to what it was evaluated on.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.core.logging import logger

_MODEL_URL = (
    "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/onnx/vision_model_quantized.onnx"
)
_MODEL_PATH = Path("data/clip/vision_model_quantized.onnx")

# openai/clip-vit-base-patch32's own preprocessor_config.json
_IMAGE_SIZE = 224
_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

_session = None  # lazy: created, and the model downloaded, only on first actual use


def _ensure_downloaded() -> Path:
    if _MODEL_PATH.exists():
        return _MODEL_PATH
    import httpx

    _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info("clip_vision_model_downloading", url=_MODEL_URL)
    tmp = _MODEL_PATH.with_suffix(".onnx.part")
    with httpx.stream("GET", _MODEL_URL, follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.rename(_MODEL_PATH)
    logger.info("clip_vision_model_downloaded", path=str(_MODEL_PATH))
    return _MODEL_PATH


def _get_session():  # noqa: ANN202
    global _session
    if _session is None:
        import onnxruntime as ort

        path = _ensure_downloaded()
        _session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return _session


def _preprocess(image_bgr: np.ndarray) -> np.ndarray:
    h, w = image_bgr.shape[:2]
    scale = _IMAGE_SIZE / min(h, w)
    nh, nw = round(h * scale), round(w * scale)
    resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_CUBIC)
    top, left = (nh - _IMAGE_SIZE) // 2, (nw - _IMAGE_SIZE) // 2
    cropped = resized[top : top + _IMAGE_SIZE, left : left + _IMAGE_SIZE]
    rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    normalized = (rgb - _MEAN) / _STD
    return normalized.transpose(2, 0, 1)[None].astype(np.float32)  # NCHW


def embed_image(image_bgr: np.ndarray) -> np.ndarray:
    """A unit-length 512-d CLIP embedding of this image. Never asks what
    kind of product this is — the same call for a watch, a gown or a
    handbag."""
    session = _get_session()
    pixel_values = _preprocess(image_bgr)
    (embedding,) = session.run(["image_embeds"], {"pixel_values": pixel_values})
    vec = embedding[0]
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))
