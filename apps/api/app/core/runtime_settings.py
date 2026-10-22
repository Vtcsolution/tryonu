"""Admin-editable overrides for a whitelisted subset of Settings.

Values live encrypted in the `app_settings` table and take precedence over
.env. Every process (API workers, the RQ worker) re-checks the table at most
every REFRESH_SECONDS and, when it changed, rebuilds Settings from env +
overrides and copies the result onto the shared cached Settings object —
everything reads settings at call time, so this takes effect without a
restart. Provider registries are lru_cached, so those caches are cleared too.

Infrastructure settings (DATABASE_URL, SECRET_KEY, REDIS_URL, CORS, cookies,
storage) are deliberately not editable here: a bad value saved from a page
backed by the database could take the site down or lock every admin out.
"""

from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.logging import logger

REFRESH_SECONDS = 15.0

Kind = Literal["secret", "text", "bool", "int", "choice"]


@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    group: str
    kind: Kind
    choices: tuple[str, ...] = ()
    help: str = ""
    min_value: int | None = None


SPECS: tuple[SettingSpec, ...] = (
    # --- AI try-on ---
    SettingSpec("VIRTUAL_TRYON_PROVIDER", "Try-on engine", "ai_tryon", "choice", ("openai", "gemini", "best_of", "fashn", "mock"),
                help="Which AI draws the try-on. openai or gemini: the whole outfit at once, shoes, bags and jewellery "
                "too. best_of: draws with both and keeps the better one (costs both). fashn: clothes one piece at a "
                "time. mock: a test picture. If the chosen one has no key, another one with a key is used."),
    SettingSpec("TRYON_OPENAI_FOR_FULL_LOOKS", "Use OpenAI for shoes, bags and jewellery", "ai_tryon", "bool",
                help="Only with FASHN tryon-v1.6 (clothes only): looks with accessories are drawn by OpenAI. If OpenAI "
                "fails, FASHN draws it."),
    SettingSpec("TRYON_QUALITY_PIPELINE", "Quality check", "ai_tryon", "bool",
                help="Keeps the person's own face, body and background, checks every item, and redraws or stops poor "
                "results. Needs the OpenAI key."),
    SettingSpec("TRYON_QUALITY_RETRIES", "Retries per item", "ai_tryon", "int", min_value=0,
                help="Extra renders when an item fails inspection — each costs one more render."),
    SettingSpec("TRYON_QUALITY_MIN_PRODUCT", "Minimum product match (0-10)", "ai_tryon", "int", min_value=0),
    SettingSpec("TRYON_QUALITY_MIN_FIT", "Minimum fit & realism (0-10)", "ai_tryon", "int", min_value=0),
    SettingSpec("TRYON_QUALITY_BEST_OF_SKIP_SCORE", "best_of: good-enough score (0-10)", "ai_tryon", "int",
                help="best_of only. If the first engine scores this or more, the second one isn't used. Lower = cheaper; "
                "higher = compares more often.", min_value=0),
    SettingSpec("OPENAI_VISION_MODEL", "Vision model (inspection)", "ai_tryon", "text",
                help="Looks at images only — never draws. e.g. gpt-5.4-mini"),
    SettingSpec("TRYON_KEEP_ORIGINAL_FACE", "Keep the person's real face", "ai_tryon", "bool",
                help="Puts the person's real face back on the result, because AI can change faces. Skipped when it can't "
                "be done safely."),
    SettingSpec("OPENAI_IMAGE_MODEL", "OpenAI try-on image model", "ai_tryon", "text",
                help="Used when the try-on provider is “openai”, e.g. gpt-image-2."),
    SettingSpec("OPENAI_IMAGE_QUALITY", "OpenAI picture quality", "ai_tryon", "choice", ("low", "medium", "high"),
                help="low: about 15 s per item and the best results. medium: about 30 s. high: about 90 s and worse. Keep "
                "on low."),
    SettingSpec("FASHN_API_KEY", "FASHN API key", "ai_tryon", "secret"),
    SettingSpec("FASHN_MODEL", "FASHN model", "ai_tryon", "choice", ("tryon-max", "tryon-v1.6"),
                help="tryon-max: clothes, shoes, bags and jewellery, and keeps the face. tryon-v1.6: clothes only."),
    SettingSpec("GEMINI_API_KEY", "Gemini API key", "ai_tryon", "secret",
                help="From Google AI Studio. Used when the try-on provider is “gemini” or “best_of”."),
    SettingSpec("GEMINI_IMAGE_MODEL", "Gemini model", "ai_tryon", "text",
                help="For example gemini-3-pro-image. Don't use gemini-2.5-flash-image: it can return the shop's model "
                "instead of the customer."),
    SettingSpec("GEMINI_IMAGE_SIZE", "Gemini picture size", "ai_tryon", "choice", ("1K", "2K", "4K"),
                help="2K is the sharpest. 1K is softer; 4K is only an enlarged 2K and looks softer."),
    # --- AI stylist ---
    SettingSpec("LLM_PROVIDER", "Stylist provider", "ai_stylist", "choice", ("openai", "mock")),
    SettingSpec("OPENAI_API_KEY", "OpenAI API key", "ai_stylist", "secret"),
    SettingSpec("OPENAI_MODEL", "OpenAI model", "ai_stylist", "text"),
    # --- retailers ---
    SettingSpec("EBAY_CLIENT_ID", "Client ID (App ID)", "ebay", "text"),
    SettingSpec("EBAY_CLIENT_SECRET", "Client secret (Cert ID)", "ebay", "secret"),
    SettingSpec("EBAY_CAMPAIGN_ID", "Partner Network campaign ID", "ebay", "text",
                help="Required to actually earn commission — from partnernetwork.ebay.com."),
    SettingSpec("EBAY_MARKETPLACE_ID", "Marketplace", "ebay", "text", help="e.g. EBAY_US, EBAY_GB, EBAY_DE"),
    SettingSpec("CJ_API_TOKEN", "Personal access token", "cj", "secret"),
    SettingSpec("CJ_WEBSITE_ID", "Website ID (PID)", "cj", "text"),
    SettingSpec("RAKUTEN_ENABLED", "Enabled", "rakuten", "bool"),
    SettingSpec("RAKUTEN_CLIENT_ID", "Client ID", "rakuten", "text"),
    SettingSpec("RAKUTEN_CLIENT_SECRET", "Client secret", "rakuten", "secret"),
    SettingSpec("RAKUTEN_TOKEN", "Access token", "rakuten", "secret"),
    SettingSpec("RAKUTEN_REFRESH_TOKEN", "Refresh token", "rakuten", "secret"),
    SettingSpec("RAKUTEN_PUBLISHER_ID", "Publisher ID (SID)", "rakuten", "text"),
    SettingSpec("RAKUTEN_ACCOUNT_ID", "Account ID", "rakuten", "text"),
    SettingSpec("AMAZON_ACCESS_KEY", "PA-API access key", "amazon", "text"),
    SettingSpec("AMAZON_SECRET_KEY", "PA-API secret key", "amazon", "secret"),
    SettingSpec("AMAZON_PARTNER_TAG", "Associates partner tag", "amazon", "text"),
    SettingSpec("FLIPKART_AFFILIATE_ID", "Affiliate ID", "flipkart", "text"),
    SettingSpec("FLIPKART_AFFILIATE_TOKEN", "Affiliate token", "flipkart", "secret"),
    SettingSpec("DARAZ_API_KEY", "API key", "daraz", "secret"),
    # --- payments ---
    SettingSpec("PAYMENT_PROVIDER", "Payments by", "payments", "choice", ("paddle", "paypal", "stripe", "mock"),
                help="paypal: real checkout. mock: test only, never charges (refused on the live site)."),
    SettingSpec("PAYPAL_MODE", "PayPal mode", "payments", "choice", ("sandbox", "live"),
                help="sandbox: test money. live: real money. Switch to live only after a sandbox test worked."),
    SettingSpec("PAYPAL_SANDBOX_CLIENT_ID", "PayPal sandbox client ID", "payments", "text"),
    SettingSpec("PAYPAL_SANDBOX_CLIENT_SECRET", "PayPal sandbox secret", "payments", "secret"),
    SettingSpec("PAYPAL_CLIENT_ID", "PayPal live client ID", "payments", "text"),
    SettingSpec("PAYPAL_CLIENT_SECRET", "PayPal live secret", "payments", "secret"),
    SettingSpec("PAYPAL_WEBHOOK_ID", "PayPal webhook ID", "payments", "text",
                help="From PayPal Developer → your app → Webhooks (address: https://<api>/api/v1/webhooks/paypal). With "
                "it, renewals and refunds arrive at once; without it, overnight."),
    SettingSpec("PADDLE_MODE", "Paddle mode", "payments", "choice", ("sandbox", "live"),
                help="sandbox: test cards, no real money. live: real money, after Paddle approved your account."),
    SettingSpec("PADDLE_SANDBOX_API_KEY", "Paddle sandbox API key", "payments", "secret",
                help="Paddle sandbox → Developer tools → Authentication. Starts with pdl_sdbx_apikey_."),
    SettingSpec("PADDLE_SANDBOX_CLIENT_TOKEN", "Paddle sandbox client-side token", "payments", "text",
                help="Starts with test_."),
    SettingSpec("PADDLE_API_KEY", "Paddle live API key", "payments", "secret"),
    SettingSpec("PADDLE_CLIENT_TOKEN", "Paddle live client-side token", "payments", "text", help="Starts with live_."),
    SettingSpec("PADDLE_WEBHOOK_SECRET", "Paddle webhook secret", "payments", "secret",
                help="From Paddle → Notifications, for https://<api>/api/v1/webhooks/paddle. Payments still work "
                "without it; with it they finish even if the customer closes the page."),
    SettingSpec("STRIPE_SECRET_KEY", "Stripe secret key", "payments", "secret"),
    SettingSpec("STRIPE_WEBHOOK_SECRET", "Stripe webhook signing secret", "payments", "secret"),
    # --- email ---
    SettingSpec("EMAIL_PROVIDER", "Email provider", "email", "choice", ("smtp", "mock")),
    SettingSpec("SMTP_HOST", "SMTP host", "email", "text"),
    SettingSpec("SMTP_PORT", "SMTP port", "email", "int", min_value=1),
    SettingSpec("SMTP_USERNAME", "SMTP username", "email", "text"),
    SettingSpec("SMTP_PASSWORD", "SMTP password", "email", "secret"),
    SettingSpec("SMTP_FROM_EMAIL", "From address", "email", "text"),
    # --- credits ---
    SettingSpec("SIGNUP_FREE_CREDITS", "Free credits on signup", "credits", "int", min_value=0),
    SettingSpec("TRYON_CREDIT_COST", "Single-item try-on cost", "credits", "int", min_value=1),
    SettingSpec("OUTFIT_TRYON_CREDIT_COST", "Outfit try-on cost", "credits", "int", min_value=1),
    SettingSpec("STORE_FASHN_CREDITS_PER_TRYON", "FASHN credits per try-on", "credits", "int",
                help="How many FASHN credits one try-on uses (4 at 2k quality). Used to show each store plan's cost and margin.",
                min_value=1),
    SettingSpec("STORE_FASHN_CREDIT_PKR", "Price of one FASHN credit (PKR)", "credits", "int",
                help="What you pay FASHN for one credit, in Pakistani rupees.", min_value=1),
    SettingSpec("SHOP_DAILY_FASHN_CREDITS", "Shopper try-ons: daily FASHN limit", "credits", "int",
                help="Most FASHN credits shopper try-ons may use in a day (about 4 per look). 0 = approve each try-on by "
                "hand.", min_value=0),
    SettingSpec("DEV_API_DAILY_TRYON_CAP", "Developer try-ons: daily limit", "credits", "int",
                help="Most API try-ons a day, for all developers together.", min_value=0),
    SettingSpec("REFERRAL_TRYON_CREDITS", "Invite reward: friend's first try-on", "credits", "int",
                help="Credits for the person who shared, when a friend they invited makes a first try-on. Once per friend. "
                "0 = off.", min_value=0),
    SettingSpec("REFERRAL_REWARD_CREDITS", "Invite reward: friend's first purchase", "credits", "int",
                help="Extra credits when that friend buys credits for the first time. 0 = off.", min_value=0),
    SettingSpec("STORE_USD_TO_PKR", "PKR per US dollar", "credits", "int",
                help="To compare try-on costs with store plan prices in dollars.", min_value=1),
    # --- help ---
    SettingSpec("SUPPORT_WHATSAPP", "Help WhatsApp number", "help", "text",
                help="Shows “Chat with us on WhatsApp”. With the country code, e.g. +92 300 1234567. Empty = hidden."),
)

SPECS_BY_KEY = {s.key: s for s in SPECS}

GROUPS: tuple[tuple[str, str], ...] = (
    ("ai_tryon", "AI try-on"),
    ("ai_stylist", "AI Stylist (OpenAI)"),
    ("ebay", "eBay"),
    ("cj", "CJ Affiliate"),
    ("rakuten", "Rakuten Advertising"),
    ("amazon", "Amazon Associates"),
    ("flipkart", "Flipkart"),
    ("daraz", "Daraz"),
    ("payments", "Payments"),
    ("email", "Email"),
    ("credits", "Credits & prices"),
    ("help", "Help & contact"),
)


class SettingsValidationError(ValueError):
    pass


def _fernet() -> Fernet:
    # Derived from SECRET_KEY, which stays .env-only. Rotating SECRET_KEY
    # makes stored overrides unreadable — they're then ignored (and flagged
    # in the panel) rather than crashing startup.
    digest = hashlib.sha256(b"tryonu-app-settings:" + get_settings().SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def build_settings(overrides: dict[str, str]) -> Settings:
    """env/.env + overrides, including Settings' own validation and its
    mock-fallback rules. Raises SettingsValidationError on a bad value."""
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(p) for p in first.get("loc", ())) or "value"
        label = SPECS_BY_KEY[field].label if field in SPECS_BY_KEY else field
        raise SettingsValidationError(f"{label}: {first.get('msg', 'invalid value')}") from exc


def validate_value(key: str, value: str) -> None:
    spec = SPECS_BY_KEY[key]
    if spec.kind == "choice" and value not in spec.choices:
        raise SettingsValidationError(f"{spec.label}: must be one of {', '.join(spec.choices)}")
    if spec.kind == "int":
        try:
            number = int(value)
        except ValueError as exc:
            raise SettingsValidationError(f"{spec.label}: must be a whole number") from exc
        if spec.min_value is not None and number < spec.min_value:
            raise SettingsValidationError(f"{spec.label}: must be at least {spec.min_value}")
    if spec.kind == "bool" and value not in ("true", "false"):
        raise SettingsValidationError(f"{spec.label}: must be true or false")


def _clear_provider_caches() -> None:
    from app.ai.llm.registry import get_stylist_provider
    from app.ai.providers.registry import get_full_look_provider, get_tryon_provider
    from app.email.registry import get_email_provider
    from app.payments.registry import get_payment_provider

    for cached in (
        get_tryon_provider,
        get_full_look_provider,
        get_stylist_provider,
        get_email_provider,
        get_payment_provider,
    ):
        cached.cache_clear()


def apply_overrides(overrides: dict[str, str]) -> None:
    fresh = build_settings(overrides)
    target = get_settings()
    for name in Settings.model_fields:
        setattr(target, name, getattr(fresh, name))
    _clear_provider_caches()


# ------------------------------------------------------------------ syncing

_applied_fingerprint = ""  # "" == no overrides, the state every process starts in
_last_check = 0.0
unreadable_keys: set[str] = set()


def _fingerprint(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    return hashlib.sha256("\n".join(f"{k}={v}" for k, v in sorted(rows)).encode()).hexdigest()


async def load_overrides() -> tuple[dict[str, str], str]:
    from app.db.session import AsyncSessionLocal
    from app.models.app_setting import AppSetting

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(AppSetting.key, AppSetting.value_encrypted))).all()

    overrides: dict[str, str] = {}
    unreadable: set[str] = set()
    for key, token in rows:
        if key not in SPECS_BY_KEY:
            continue
        value = decrypt(token)
        if value is None:
            unreadable.add(key)
            continue
        overrides[key] = value
    unreadable_keys.clear()
    unreadable_keys.update(unreadable)
    return overrides, _fingerprint([(k, v) for k, v in rows])


async def refresh_if_stale(*, force: bool = False) -> None:
    global _applied_fingerprint, _last_check

    if not force and time.monotonic() - _last_check < REFRESH_SECONDS:
        return
    # Claim the window before awaiting so concurrent requests don't all
    # query at once; a duplicate apply of identical overrides is harmless.
    _last_check = time.monotonic()
    try:
        overrides, fingerprint = await load_overrides()
        if fingerprint != _applied_fingerprint:
            apply_overrides(overrides)
            _applied_fingerprint = fingerprint
            logger.info("runtime_settings_applied", keys=sorted(overrides))
    except SettingsValidationError as exc:
        logger.error("runtime_settings_invalid", error=str(exc))
    except Exception as exc:  # noqa: BLE001 — e.g. table not migrated yet; keep serving on .env values
        logger.warning("runtime_settings_refresh_failed", error=str(exc))
