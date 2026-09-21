"""
Central runtime configuration.

Everything here has a safe local-dev default (SQLite on disk, local file
storage, an in-process job runner, a mock AI provider) so the API is fully
runnable with zero external services. Production sets the corresponding env
vars (DATABASE_URL, REDIS_URL, S3_*, FASHN_API_KEY, ...) and the same code
path switches to Postgres + Redis/RQ + S3/R2 + the real FASHN provider —
nothing in application code branches on "are we in prod", only these
settings do.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    PROJECT_NAME: str = "TryOnU API"
    ENV: Literal["development", "staging", "production"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    # Absolute base URL this API is reachable at — used to turn a local-disk
    # signed path ("/media/...") into an absolute URL when handing an image
    # off to an external AI provider that needs to fetch it itself.
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"
    SECRET_KEY: str = "dev-secret-change-me-in-production"  # noqa: S105
    DEBUG: bool = True

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # --- database ---
    # Local dev default: file-based SQLite, zero setup required.
    # Production: postgresql+asyncpg://user:pass@host:5432/tryonu
    DATABASE_URL: str = "sqlite+aiosqlite:///./tryonu.db"

    # --- redis / queue ---
    # When unset, the job queue falls back to an in-process asyncio runner
    # (see app/services/queue.py) — same interface, no Redis required to
    # develop or to run the test suite.
    REDIS_URL: str | None = None

    # --- auth ---
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    COOKIE_DOMAIN: str | None = None
    COOKIE_SECURE: bool = False  # set True behind HTTPS in production

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None

    # --- object storage (S3 / Cloudflare R2) ---
    # When S3_ENDPOINT_URL / keys are unset, files are written to local disk
    # under STORAGE_LOCAL_DIR and served from /media (dev only). Each also
    # accepts the shorter S3_ENDPOINT / S3_ACCESS_KEY / S3_SECRET_KEY names.
    S3_ENDPOINT_URL: str | None = Field(
        default=None, validation_alias=AliasChoices("S3_ENDPOINT_URL", "S3_ENDPOINT")
    )
    S3_ACCESS_KEY_ID: str | None = Field(
        default=None, validation_alias=AliasChoices("S3_ACCESS_KEY_ID", "S3_ACCESS_KEY")
    )
    S3_SECRET_ACCESS_KEY: str | None = Field(
        default=None, validation_alias=AliasChoices("S3_SECRET_ACCESS_KEY", "S3_SECRET_KEY")
    )
    S3_BUCKET: str = "tryonu-media"
    S3_REGION: str = "auto"
    S3_PUBLIC_BASE_URL: str | None = None  # CDN/public URL prefix, if any
    STORAGE_LOCAL_DIR: str = "storage"
    SIGNED_URL_TTL_SECONDS: int = 900

    # --- uploads ---
    MAX_UPLOAD_BYTES: int = 12 * 1024 * 1024
    ALLOWED_IMAGE_CONTENT_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
    ]

    # --- credits ---
    SIGNUP_FREE_CREDITS: int = 100
    TRYON_CREDIT_COST: int = 5
    OUTFIT_TRYON_CREDIT_COST: int = 8

    # --- AI providers ---
    # "mock" needs no credentials and simulates a realistic job lifecycle —
    # used automatically whenever the real provider has no API key set.
    VIRTUAL_TRYON_PROVIDER: Literal["fashn", "openai", "mock"] = "mock"
    FASHN_API_KEY: str | None = None
    FASHN_API_BASE_URL: str = "https://api.fashn.ai/v1"
    FASHN_MODEL: Literal["tryon-v1.6", "tryon-max"] = "tryon-v1.6"

    LLM_PROVIDER: Literal["openai", "mock"] = "mock"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    # try-on via OpenAI image editing (VIRTUAL_TRYON_PROVIDER=openai)
    OPENAI_IMAGE_MODEL: str = "gpt-image-2"  # measured: changes 0.2% of the body for a watch-only edit (gpt-image-1: 8.7%)
    # Measured per render (shirt/dress/shoes/bag/watch): "low" ~15s and scored
    # 8-9, "medium" ~32s, "high" ~87s and scored WORSE (it redraws more of the
    # photo instead of reproducing the product). Speed here is free quality.
    OPENAI_IMAGE_QUALITY: Literal["low", "medium", "high"] = "low"
    # looks at images (product analysis, locating the worn item, quality checks) — never draws
    OPENAI_VISION_MODEL: str = "gpt-5.4-mini"
    # with the FASHN provider: render outfits that include shoes, bags or
    # jewellery with OpenAI instead (FASHN can't draw those), falling back
    # to FASHN if OpenAI fails. Needs OPENAI_API_KEY.
    TRYON_OPENAI_FOR_FULL_LOOKS: bool = False  # FASHN tryon-max draws every wearable itself
    # put the person's own face back on every try-on result (see
    # app/services/face_restore.py) — models redraw faces and they drift
    TRYON_KEEP_ORIGINAL_FACE: bool = True
    # the quality pipeline (app/services/tryon_quality): keep the person's own
    # pixels outside the product, grade every item, retry or refuse bad renders
    TRYON_QUALITY_PIPELINE: bool = True
    TRYON_QUALITY_RETRIES: int = 1  # extra renders per item when a render fails inspection
    TRYON_QUALITY_MIN_PRODUCT: int = 7  # 0-10: exact product (colour, pattern, logo, hardware)
    TRYON_QUALITY_MIN_FIT: int = 6  # 0-10: worn correctly, and realism
    EMBEDDING_DIM: int = 1536

    # --- retailer / affiliate credentials (each optional; the adapter
    # skips itself with a clear message when unset — see app/retailers/*) ---
    AMAZON_ACCESS_KEY: str | None = None
    AMAZON_SECRET_KEY: str | None = None
    AMAZON_PARTNER_TAG: str | None = None
    EBAY_CLIENT_ID: str | None = None
    EBAY_CLIENT_SECRET: str | None = None
    EBAY_CAMPAIGN_ID: str | None = None
    EBAY_MARKETPLACE_ID: str = "EBAY_US"
    FLIPKART_AFFILIATE_ID: str | None = None
    FLIPKART_AFFILIATE_TOKEN: str | None = None
    DARAZ_API_KEY: str | None = None

    # Rakuten Advertising — off by default even with credentials present,
    # since this integration hasn't been live-verified yet (see
    # app/retailers/rakuten.py). Flip on only once real credentials are
    # confirmed working end-to-end.
    RAKUTEN_ENABLED: bool = False
    RAKUTEN_CLIENT_ID: str | None = None
    RAKUTEN_CLIENT_SECRET: str | None = None
    # A directly-issued access token (some Rakuten account setups skip
    # client_credentials and hand you a token + refresh token instead) —
    # used in preference to CLIENT_ID/SECRET when set.
    RAKUTEN_TOKEN: str | None = None
    RAKUTEN_REFRESH_TOKEN: str | None = None
    RAKUTEN_PUBLISHER_ID: str | None = None
    RAKUTEN_ACCOUNT_ID: str | None = None
    # Confirmed live: api.rakutenmarketing.com does not resolve at all;
    # api.linksynergy.com is Rakuten Advertising's real, working API host
    # (the /token and /v2/advertisers endpoints were verified against it).
    RAKUTEN_API_BASE_URL: str = "https://api.linksynergy.com"

    # --- affiliate networks (distinct from retailers — a network like Awin
    # provides the tracking/commission layer across multiple retailers) ---
    AWIN_API_TOKEN: str | None = None
    AWIN_PUBLISHER_ID: str | None = None
    CJ_API_TOKEN: str | None = None
    CJ_WEBSITE_ID: str | None = None
    IMPACT_ACCOUNT_SID: str | None = None
    IMPACT_AUTH_TOKEN: str | None = None

    # --- payments ---
    PAYMENT_PROVIDER: Literal["stripe", "mock"] = "mock"
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # --- email (password reset, etc.) ---
    EMAIL_PROVIDER: Literal["smtp", "mock"] = "mock"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@tryonu.ai"
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 1440

    # --- visitor analytics ---
    # DB-IP "IP to Country Lite" (CC BY 4.0) — looked up locally, so visitor
    # IPs are never sent to a third party. Downloaded automatically on
    # startup when missing (or run `python -m app.scripts.update_geoip`).
    GEOIP_DB_PATH: str = "data/geoip/dbip-country-lite.mmdb"
    GEOIP_AUTO_DOWNLOAD: bool = True

    # --- rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_TRYON_PER_HOUR: int = 30

    # --- frontend ---
    FRONTEND_URL: AnyHttpUrl = "http://localhost:3000"  # type: ignore[assignment]

    @model_validator(mode="after")
    def _fallback_to_mock_without_key(self) -> "Settings":
        # Never hard-fail because a key is missing — degrade to mock so the
        # rest of the stack (jobs, credits, storage) stays testable.
        if self.VIRTUAL_TRYON_PROVIDER == "fashn" and not self.FASHN_API_KEY:
            self.VIRTUAL_TRYON_PROVIDER = "mock"
        if self.VIRTUAL_TRYON_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            self.VIRTUAL_TRYON_PROVIDER = "mock"
        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            self.LLM_PROVIDER = "mock"
        if self.PAYMENT_PROVIDER == "stripe" and not self.STRIPE_SECRET_KEY:
            self.PAYMENT_PROVIDER = "mock"
        if self.EMAIL_PROVIDER == "smtp" and not self.SMTP_HOST:
            self.EMAIL_PROVIDER = "mock"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
