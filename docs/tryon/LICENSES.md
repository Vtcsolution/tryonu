# Models and weights used by the try-on pipeline

Every model/weight used anywhere in the production path, its license, and its commercial status. Anything not listed here is not used in production code — a `research/`-only or `UNVERIFIED` entry would be called out explicitly if one existed.

| Model/weight | Used for | License | Commercial use | Notes |
|---|---|---|---|---|
| `rembg` (library) | Wrapper around the cutout model below | MIT | Yes | [PyPI](https://pypi.org/project/rembg/) |
| `u2netp` (ONNX weights, via `rembg`) | Product-photo background removal, for colour verification (`cutout.py`) | Apache 2.0 | Yes | Downloaded automatically on first use from `rembg`'s own GitHub release (`danielgatis/rembg`), cached locally (`~/.rembg/models/`) — never at import time, only when a cutout is actually requested |
| `u2net_human_seg` (ONNX weights, via `rembg`) | Finding a model's hand, arm or face in an accessory photo, so it is left off the try-on look board (`cutout.py`'s `person_mask`) | Apache 2.0 (U-2-Net) | Yes | Downloaded automatically on first use from `rembg`'s GitHub release (~176 MB), cached locally (`~/.rembg/models/`) |
| `onnxruntime` | Runs the ONNX models in this table, CPU only | MIT | Yes | No GPU required or used |
| CLIP ViT-B/32 vision encoder (ONNX, via `Xenova/clip-vit-base-patch32`) | Image embeddings for shadow-mode distractor ranking (`clip_embed.py`, `distractor_rank.py`) | MIT | Yes | The underlying weights are OpenAI's own `openai/clip-vit-base-patch32` (MIT — [github.com/openai/CLIP](https://github.com/openai/CLIP)); the Hugging Face repo used is a straight ONNX weight conversion for Transformers.js (same `base_model`, no retraining), not a separately-licensed model. The int8-quantized vision-only export (~89MB) is downloaded automatically on first use, cached at `data/clip/vision_model_quantized.onnx` — never at import time. |

**Explicitly not used:** `rembg` also supports other models — notably `RMBG-2.0`, which is BRIA-licensed and requires a paid commercial agreement. The codebase must only ever request `"u2netp"` and `"u2net_human_seg"` by name (`cutout.py`'s `_MODEL_NAME` and `_PERSON_MODEL` constants) — never a bare default that could silently resolve to a different, non-commercial model.

No GPU-dependent or research-only model is used anywhere in the production path as of this entry.
