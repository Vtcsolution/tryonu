"""Virtual try-on provider abstraction.

The rest of the app (job worker, API) only ever talks to this interface —
never to FASHN's (or anyone else's) HTTP API directly. Adding a new
provider is: implement this ABC, register it in registry.py, done; no
other file changes. The provider is handed the *real* product image URL
and must render onto it, never substitute a different garment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class TryOnProviderError(Exception):
    """Raised for both transient (retryable) and permanent provider failures."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class TryOnInput:
    model_image_url: str
    garment_image_url: str
    # "auto" lets the provider infer top/bottom/full-body from the image.
    category: str = "auto"
    # free-text instructions (tryon-max only), e.g. "layer this over the outfit"
    prompt: str = ""
    # fixed for reproducibility; a different seed gives a genuinely different render
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class OutfitPiece:
    """One product to put on the person in a whole-outfit render."""

    image_url: str
    slot: str  # OutfitSlot value: dress, top, shoes, bag, accessory, ...
    name: str


@dataclass(frozen=True, slots=True)
class TryOnOutput:
    image_bytes: bytes
    content_type: str = "image/jpeg"
    provider_job_id: str | None = None
    latency_ms: int | None = None


class VirtualTryOnProvider(ABC):
    #: config value clients use to select this provider (app.core.config.VIRTUAL_TRYON_PROVIDER)
    name: str
    #: the specific model/version, recorded on every TryOnJob for auditability
    model: str

    #: True when the provider dresses the person in a whole outfit in ONE
    #: render (generate_outfit) — every item at once, shoes/bags/jewellery
    #: included — instead of one garment per call chained together.
    whole_outfit: bool = False

    @abstractmethod
    async def generate(self, payload: TryOnInput) -> TryOnOutput:
        """Runs the full submit -> poll -> download cycle and returns the
        final image bytes, or raises TryOnProviderError."""
        ...

    async def generate_outfit(self, model_image_url: str, pieces: list[OutfitPiece]) -> TryOnOutput:
        raise NotImplementedError
