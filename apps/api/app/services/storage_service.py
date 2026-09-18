"""Object storage abstraction.

Production: S3 or Cloudflare R2 (R2 is S3-API-compatible — just point
S3_ENDPOINT_URL at it). The bucket is treated as fully private; every read
goes through a short-lived presigned URL, never a permanent public link.

Local dev (no S3_* configured): files land on local disk under
STORAGE_LOCAL_DIR and are served through `/media/<key>?exp=&sig=`, an
HMAC-signed URL with the same TTL semantics as a real presigned S3 URL —
so "signed private URL" is true in dev too, not just in prod.
"""

from __future__ import annotations

import hashlib
import hmac
import mimetypes
import time
from abc import ABC, abstractmethod
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import get_settings

settings = get_settings()


class StorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, content: bytes, content_type: str) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def signed_url(self, key: str, ttl_seconds: int | None = None) -> str: ...


class S3StorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(signature_version="s3v4"),
        )
        self._bucket = settings.S3_BUCKET

    def put(self, key: str, content: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            # bucket-private by default; never ACL="public-read"
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def read(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def signed_url(self, key: str, ttl_seconds: int | None = None) -> str:
        if settings.S3_PUBLIC_BASE_URL:
            # Fronted by a CDN issuing its own signed URLs (e.g. CloudFront) —
            # application code still only ever hands out this one URL shape.
            return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl_seconds or settings.SIGNED_URL_TTL_SECONDS,
        )


class LocalDiskStorageBackend(StorageBackend):
    """Dev-only. Signs URLs with HMAC-SHA256 over (key, expiry, SECRET_KEY),
    verified by the /media route in app/api/v1/endpoints/media.py."""

    def __init__(self) -> None:
        self._root = Path(settings.STORAGE_LOCAL_DIR)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self._root / key).resolve()
        if self._root.resolve() not in p.parents and p != self._root.resolve():
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, content: bytes, content_type: str) -> None:  # noqa: ARG002
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def signed_url(self, key: str, ttl_seconds: int | None = None) -> str:
        exp = int(time.time()) + (ttl_seconds or settings.SIGNED_URL_TTL_SECONDS)
        sig = _sign(key, exp)
        # Relative path — the API's own PUBLIC_API_BASE_URL is prefixed by
        # whoever needs an absolute URL (e.g. the try-on worker).
        return f"/media/{key}?exp={exp}&sig={sig}"


def _sign(key: str, exp: int) -> str:
    msg = f"{key}:{exp}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def verify_local_signature(key: str, exp: int, sig: str) -> bool:
    if time.time() > exp:
        return False
    expected = _sign(key, exp)
    return hmac.compare_digest(expected, sig)


def local_storage_root() -> Path:
    return Path(settings.STORAGE_LOCAL_DIR)


def is_s3_configured() -> bool:
    return bool(settings.S3_ENDPOINT_URL or (settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY))


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = S3StorageBackend() if is_s3_configured() else LocalDiskStorageBackend()
    return _backend


def fresh_url(storage_key: str | None, stored_url: str | None) -> str | None:
    """A newly signed URL for a stored file. Signed URLs expire
    (SIGNED_URL_TTL_SECONDS), so the one saved at upload time is never
    handed out again — it broke photos, results and try-ons 15 minutes in.
    No key (e.g. an external image) means the stored URL is the real one."""
    return get_storage().signed_url(storage_key) if storage_key else stored_url


def guess_content_type(filename: str, default: str = "application/octet-stream") -> str:
    return mimetypes.guess_type(filename)[0] or default


def new_key(*parts: str) -> str:
    return "/".join(p.strip("/") for p in parts)
