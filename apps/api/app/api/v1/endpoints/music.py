"""The free music library: admins add songs TryOnU may use (royalty-free or our
own), members pick one for a post, and it plays with the post in Reels.

Only songs an admin added can be picked, so nothing copyrighted is ever
uploaded by members."""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.models.community import CommunityPost, MusicTrack
from app.services.storage_service import get_storage, new_key

router = APIRouter(prefix="/community/music", tags=["community"])
admin_router = APIRouter(prefix="/admin/community/music", tags=["admin"])

MAX_MB = 12
MOODS = ("happy", "chill", "party", "romantic", "desi", "classic")


def audio_kind(raw: bytes) -> tuple[str, str] | None:
    """(extension, content type) of an MP3, M4A, OGG or WAV file, or None."""
    head = raw[:12]
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "mp3", "audio/mpeg"
    if head[4:8] == b"ftyp":
        return "m4a", "audio/mp4"
    if head[:4] == b"OggS":
        return "ogg", "audio/ogg"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav", "audio/wav"
    return None


class MusicOut(BaseModel):
    id: str
    title: str
    artist: str | None
    mood: str | None
    url: str


class AdminMusicOut(MusicOut):
    is_active: bool
    uses: int
    size_bytes: int
    created_at: datetime


class MusicUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    artist: str | None = Field(default=None, max_length=120)
    mood: str | None = Field(default=None, max_length=24)
    is_active: bool | None = None


def music_out(track: MusicTrack) -> MusicOut:
    return MusicOut(
        id=track.id, title=track.title, artist=track.artist, mood=track.mood, url=get_storage().signed_url(track.storage_key)
    )


async def tracks_for(db: AsyncSession, posts: list[CommunityPost]) -> dict[str, MusicOut]:
    """The songs on these posts, by track id (a song an admin turned off still plays on old posts)."""
    ids = {p.music_track_id for p in posts if p.music_track_id}
    if not ids:
        return {}
    rows = (await db.execute(select(MusicTrack).where(MusicTrack.id.in_(ids)))).scalars()
    return {t.id: music_out(t) for t in rows}


async def pick(db: AsyncSession, track_id: str | None) -> str | None:
    """A song a member chose for a new post: must be in the library and turned on."""
    if not track_id:
        return None
    track = await db.get(MusicTrack, track_id)
    if track is None or not track.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That song isn't in the music library any more.")
    await db.execute(update(MusicTrack).where(MusicTrack.id == track.id).values(uses=MusicTrack.uses + 1))
    return track.id


def _mood(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    if not value:
        return None
    if value not in MOODS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Mood must be one of: {', '.join(MOODS)}")
    return value


# ------------------------------------------------------------------ members


@router.get("", response_model=list[MusicOut])
async def list_music(_: CurrentUser, db: DbSession):
    """Every song members can add to a post, the most used first."""
    rows = (
        await db.execute(
            select(MusicTrack).where(MusicTrack.is_active.is_(True)).order_by(MusicTrack.uses.desc(), MusicTrack.title)
        )
    ).scalars()
    return [music_out(t) for t in rows]


# ------------------------------------------------------------------ admin


def _admin_out(t: MusicTrack) -> AdminMusicOut:
    return AdminMusicOut(
        **music_out(t).model_dump(), is_active=t.is_active, uses=t.uses, size_bytes=t.size_bytes, created_at=t.created_at
    )


@admin_router.get("", response_model=list[AdminMusicOut])
async def admin_list_music(_: AdminUser, db: DbSession):
    rows = (await db.execute(select(MusicTrack).order_by(MusicTrack.created_at.desc()))).scalars()
    return [_admin_out(t) for t in rows]


@admin_router.post("", response_model=AdminMusicOut, status_code=status.HTTP_201_CREATED)
async def admin_add_music(
    _: AdminUser,
    db: DbSession,
    file: UploadFile = File(...),
    title: str = Form(min_length=1, max_length=120),
    artist: str | None = Form(default=None, max_length=120),
    mood: str | None = Form(default=None, max_length=24),
):
    raw = await file.read()
    if len(raw) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Please use a song file under {MAX_MB} MB.")
    kind = audio_kind(raw)
    if kind is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That isn't a song file we can play. Use MP3, M4A, OGG or WAV.")
    ext, content_type = kind
    key = new_key("community", "music", "library", f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{ext}")
    await asyncio.to_thread(get_storage().put, key, raw, content_type)
    track = MusicTrack(
        title=title.strip(), artist=(artist or "").strip() or None, mood=_mood(mood), storage_key=key,
        content_type=content_type, size_bytes=len(raw),
    )
    db.add(track)
    await db.commit()
    await db.refresh(track)
    return _admin_out(track)


@admin_router.patch("/{track_id}", response_model=AdminMusicOut)
async def admin_update_music(track_id: str, payload: MusicUpdateIn, _: AdminUser, db: DbSession):
    track = await db.get(MusicTrack, track_id)
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found")
    data = payload.model_dump(exclude_unset=True)
    if "mood" in data:
        data["mood"] = _mood(data["mood"])
    if "artist" in data:
        data["artist"] = (data["artist"] or "").strip() or None
    for field, value in data.items():
        setattr(track, field, value)
    await db.commit()
    await db.refresh(track)
    return _admin_out(track)


@admin_router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_music(track_id: str, _: AdminUser, db: DbSession):
    """Gone from the library and from every post that used it."""
    track = await db.get(MusicTrack, track_id)
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found")
    key = track.storage_key
    await db.execute(update(CommunityPost).where(CommunityPost.music_track_id == track.id).values(music_track_id=None))
    await db.delete(track)
    await db.commit()
    try:
        await asyncio.to_thread(get_storage().delete, key)
    except Exception:  # noqa: BLE001 — the row is gone; a leftover file is harmless
        pass
