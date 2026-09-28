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
    note: str = ""  # a correction from the quality inspector, for a retry
    description: str = ""  # what the product photo shows, read off it beforehand


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
    #: Does this engine give the person back unchanged?
    #:
    #: Everything in tryon_quality exists to undo an engine that does
    #: not: find what changed, decide which of those changes are the
    #: product, paste only those onto the customer's own pixels. That
    #: step is where every compositing artifact comes from — a seam
    #: across a collarbone, hair replaced by a chandelier, a scrap of
    #: dupatta floating beside a knee. An engine that preserves the
    #: person needs none of it, and its render is used as it comes back.
    preserves_person: bool = False
    #: Can this engine take a real edit mask — draw only where told to,
    #: with everywhere else protected by the API itself rather than by
    #: anything we do afterwards? The strongest guarantee available: not
    #: "the model usually leaves this alone" (preserves_person) or "we
    #: reconstructed protection from a diff" (the merge pipeline), but
    #: the API refusing to touch those pixels in the first place. See
    #: edit_masked() below and app/services/tryon_quality/masked.py.
    supports_masked_edit: bool = False

    @abstractmethod
    async def generate(self, payload: TryOnInput) -> TryOnOutput:
        """Runs the full submit -> poll -> download cycle and returns the
        final image bytes, or raises TryOnProviderError."""
        ...

    async def generate_outfit(self, model_image_url: str, pieces: list[OutfitPiece]) -> TryOnOutput:
        raise NotImplementedError

    async def edit_masked(self, person_png: bytes, mask_png: bytes, piece: OutfitPiece) -> TryOnOutput:
        """One product, drawn only where `mask_png`'s alpha is
        transparent. Only meaningful when supports_masked_edit is True."""
        raise NotImplementedError
