# Models and weights used by the try-on pipeline

Every model/weight used anywhere in the production path, its license, and its commercial status. Anything not listed here is not used in production code — a `research/`-only or `UNVERIFIED` entry would be called out explicitly if one existed.

| Model/weight | Used for | License | Commercial use | Notes |
|---|---|---|---|---|
| `rembg` (library) | Wrapper around the cutout model below | MIT | Yes | [PyPI](https://pypi.org/project/rembg/) |
| `u2netp` (ONNX weights, via `rembg`) | Product-photo background removal, for colour verification (`cutout.py`) | Apache 2.0 | Yes | Downloaded automatically on first use from `rembg`'s own GitHub release (`danielgatis/rembg`), cached locally (`~/.rembg/models/`) — never at import time, only when a cutout is actually requested |
| `onnxruntime` | Runs the ONNX model above, CPU only | MIT | Yes | No GPU required or used |

**Explicitly not used:** `rembg` also supports other models — notably `RMBG-2.0`, which is BRIA-licensed and requires a paid commercial agreement. The codebase must only ever request `"u2netp"` by name (`cutout.py`'s `_MODEL_NAME` constant) — never a bare default that could silently resolve to a different, non-commercial model.

No GPU-dependent or research-only model is used anywhere in the production path as of this entry.
