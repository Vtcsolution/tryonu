from __future__ import annotations

from datetime import datetime

from app.models.enums import PhotoKind
from app.schemas.common import ORMModel


class UserPhotoOut(ORMModel):
    id: str
    kind: PhotoKind
    url: str
    width: int | None
    height: int | None
    is_primary: bool
    created_at: datetime


class FittingProfileStatus(ORMModel):
    photos: list[UserPhotoOut]
    has_front: bool
    has_back: bool
    is_ready: bool
    min_required: int = 2
