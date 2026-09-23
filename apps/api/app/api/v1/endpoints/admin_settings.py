"""Admin-editable integration settings and API keys. Secret values are
write-only through this API: responses only ever carry a masked tail."""

from __future__ import annotations

import asyncio
import smtplib

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.core.config import Settings, get_settings
from app.core.deps import AdminUser, DbSession
from app.core.runtime_settings import (
    GROUPS,
    SPECS,
    SPECS_BY_KEY,
    SettingsValidationError,
    build_settings,
    encrypt,
    load_overrides,
    refresh_if_stale,
    unreadable_keys,
    validate_value,
)
from app.models.admin_audit import AdminAuditLog
from app.models.app_setting import AppSetting
from app.retailers.errors import RetailerNotConfiguredError
from app.retailers.registry import get_all_providers

router = APIRouter(prefix="/admin/settings", tags=["admin"])

_RETAILER_GROUPS = {"ebay", "cj", "rakuten", "amazon", "flipkart", "daraz"}
_TESTABLE_GROUPS = {"ai_tryon", "ai_stylist", "payments", "email"} | _RETAILER_GROUPS


class SettingFieldOut(BaseModel):
    key: str
    label: str
    kind: str
    choices: list[str]
    help: str
    source: str  # "admin" | "env" | "default"
    is_set: bool
    value: str | None  # secrets: masked tail only
    unreadable: bool
    warning: str | None


class SettingGroupOut(BaseModel):
    id: str
    label: str
    testable: bool
    fields: list[SettingFieldOut]


class SettingsOut(BaseModel):
    groups: list[SettingGroupOut]


class SettingsUpdate(BaseModel):
    # null clears the admin override, reverting that key to .env/default
    values: dict[str, str | None]


class ConnectionTestOut(BaseModel):
    ok: bool
    message: str


def _mask(value: str) -> str:
    return "••••" + value[-4:] if len(value) > 8 else "••••"


def _display(settings: Settings, key: str) -> tuple[bool, str | None]:
    raw = getattr(settings, key)
    if raw is None or raw == "":
        return False, None
    if SPECS_BY_KEY[key].kind == "secret":
        return True, _mask(str(raw))
    if isinstance(raw, bool):
        return True, "true" if raw else "false"
    return True, str(raw)


_PROVIDER_KEY_FOR = {
    "VIRTUAL_TRYON_PROVIDER": ("fashn", "FASHN API key"),
    "LLM_PROVIDER": ("openai", "OpenAI API key"),
    "PAYMENT_PROVIDER": ("stripe", "Stripe secret key"),
    "EMAIL_PROVIDER": ("smtp", "SMTP host"),
}


async def _settings_payload() -> SettingsOut:
    await refresh_if_stale(force=True)
    overrides, _ = await load_overrides()
    effective = get_settings()
    from_env = Settings().model_fields_set

    groups: list[SettingGroupOut] = []
    for group_id, group_label in GROUPS:
        fields = []
        for spec in (s for s in SPECS if s.group == group_id):
            is_set, value = _display(effective, spec.key)
            source = "admin" if spec.key in overrides else "env" if spec.key in from_env else "default"
            warning = None
            wanted = overrides.get(spec.key)
            if spec.key in _PROVIDER_KEY_FOR and wanted and wanted != value:
                real, needs = _PROVIDER_KEY_FOR[spec.key]
                if wanted == real:
                    warning = f"Saved as “{real}”, but running as mock because the {needs} is missing."
            fields.append(
                SettingFieldOut(
                    key=spec.key,
                    label=spec.label,
                    kind=spec.kind,
                    choices=list(spec.choices),
                    help=spec.help,
                    source=source,
                    is_set=is_set,
                    value=value,
                    unreadable=spec.key in unreadable_keys,
                    warning=warning,
                )
            )
        groups.append(SettingGroupOut(id=group_id, label=group_label, testable=group_id in _TESTABLE_GROUPS, fields=fields))
    return SettingsOut(groups=groups)


@router.get("", response_model=SettingsOut)
async def get_settings_panel(_: AdminUser):
    return await _settings_payload()


@router.put("", response_model=SettingsOut)
async def update_settings(payload: SettingsUpdate, admin: AdminUser, db: DbSession):
    unknown = [k for k in payload.values if k not in SPECS_BY_KEY]
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not editable here: {', '.join(unknown)}")
    if not payload.values:
        return await _settings_payload()

    to_set: dict[str, str] = {}
    to_clear: list[str] = []
    for key, value in payload.values.items():
        if value is None:
            to_clear.append(key)
            continue
        value = value.strip()
        try:
            validate_value(key, value)
        except SettingsValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        to_set[key] = value

    current, _ = await load_overrides()
    prospective = {k: v for k, v in current.items() if k not in to_clear} | to_set
    try:
        build_settings(prospective)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if to_clear:
        await db.execute(delete(AppSetting).where(AppSetting.key.in_(to_clear)))
    existing = {
        row.key: row
        for row in (await db.execute(select(AppSetting).where(AppSetting.key.in_(list(to_set))))).scalars().all()
    }
    for key, value in to_set.items():
        row = existing.get(key)
        if row is None:
            db.add(AppSetting(key=key, value_encrypted=encrypt(value), updated_by_id=admin.id))
        else:
            row.value_encrypted = encrypt(value)
            row.updated_by_id = admin.id

    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action="settings.update",
            target_type="settings",
            target_id=",".join(sorted(payload.values))[:64],
            detail={
                "set": {k: ("(secret changed)" if SPECS_BY_KEY[k].kind == "secret" else v) for k, v in to_set.items()},
                "reverted_to_env": to_clear,
            },
        )
    )
    await db.commit()
    return await _settings_payload()


# ------------------------------------------------------------------ connection tests


def _redact(message: str, settings: Settings) -> str:
    for spec in SPECS:
        if spec.kind != "secret":
            continue
        secret = getattr(settings, spec.key)
        if secret and len(secret) >= 4:
            message = message.replace(secret, "••••")
    return message[:300]


async def _test_fashn(s: Settings) -> ConnectionTestOut:
    if not s.FASHN_API_KEY:
        return ConnectionTestOut(ok=False, message="No FASHN API key set — try-on is running in mock mode.")
    # An empty "inputs" object is rejected by input validation (400) only
    # after the key is accepted; a bad key 401s first. No render is started.
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{s.FASHN_API_BASE_URL.rstrip('/')}/run",
            headers={"Authorization": f"Bearer {s.FASHN_API_KEY}"},
            json={"model_name": s.FASHN_MODEL, "inputs": {}},
        )
    if resp.status_code in (401, 403):
        return ConnectionTestOut(ok=False, message="FASHN rejected this API key.")
    if resp.status_code == 400:
        mode = "" if s.VIRTUAL_TRYON_PROVIDER == "fashn" else " (but the try-on provider is still set to mock)"
        return ConnectionTestOut(ok=True, message=f"API key accepted for {s.FASHN_MODEL}{mode}.")
    return ConnectionTestOut(ok=False, message=f"Unexpected response from FASHN: HTTP {resp.status_code}.")


async def _test_openai(s: Settings) -> ConnectionTestOut:
    if not s.OPENAI_API_KEY:
        return ConnectionTestOut(ok=False, message="No OpenAI API key set — the stylist is running in mock mode.")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"https://api.openai.com/v1/models/{s.OPENAI_MODEL}",
            headers={"Authorization": f"Bearer {s.OPENAI_API_KEY}"},
        )
    if resp.status_code == 200:
        return ConnectionTestOut(ok=True, message=f"API key accepted; model {s.OPENAI_MODEL} is available.")
    if resp.status_code == 401:
        return ConnectionTestOut(ok=False, message="OpenAI rejected this API key.")
    if resp.status_code == 404:
        return ConnectionTestOut(ok=False, message=f"API key works, but model “{s.OPENAI_MODEL}” isn't available to it.")
    return ConnectionTestOut(ok=False, message=f"Unexpected response from OpenAI: HTTP {resp.status_code}.")


async def _test_stripe(s: Settings) -> ConnectionTestOut:
    if not s.STRIPE_SECRET_KEY:
        return ConnectionTestOut(ok=False, message="No Stripe key set — payments are in mock mode (nobody is charged).")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.stripe.com/v1/balance", auth=(s.STRIPE_SECRET_KEY, ""))
    if resp.status_code == 200:
        mode = "LIVE mode" if s.STRIPE_SECRET_KEY.startswith(("sk_live", "rk_live")) else "test mode"
        extra = "" if s.PAYMENT_PROVIDER == "stripe" else " The payment provider is still set to mock."
        webhook = "" if s.STRIPE_WEBHOOK_SECRET else " Webhook signing secret is not set."
        return ConnectionTestOut(ok=True, message=f"Key accepted ({mode}).{extra}{webhook}")
    if resp.status_code == 401:
        return ConnectionTestOut(ok=False, message="Stripe rejected this secret key.")
    return ConnectionTestOut(ok=False, message=f"Unexpected response from Stripe: HTTP {resp.status_code}.")


def _smtp_check(s: Settings) -> ConnectionTestOut:
    # same connection path SMTPEmailProvider uses to send; no email is sent
    with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=10) as server:  # type: ignore[arg-type]
        server.starttls()
        if s.SMTP_USERNAME and s.SMTP_PASSWORD:
            server.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
    return ConnectionTestOut(ok=True, message=f"Connected to {s.SMTP_HOST}:{s.SMTP_PORT} and signed in.")


async def _test_smtp(s: Settings) -> ConnectionTestOut:
    if not s.SMTP_HOST:
        return ConnectionTestOut(ok=False, message="No SMTP host set — emails are only logged (mock mode).")
    try:
        return await asyncio.to_thread(_smtp_check, s)
    except smtplib.SMTPAuthenticationError:
        return ConnectionTestOut(ok=False, message="SMTP server rejected the username/password.")


async def _test_retailer(slug: str, s: Settings) -> ConnectionTestOut:
    provider = next((p for p in get_all_providers() if p.slug == slug), None)
    if provider is None:
        return ConnectionTestOut(ok=False, message="Retailer isn't registered.")
    try:
        results = await provider.search_live(query="shirt", limit=1)
    except NotImplementedError:
        return ConnectionTestOut(ok=False, message=f"{provider.display_name} integration isn't built yet — saving keys won't enable search.")
    except RetailerNotConfiguredError as exc:
        # a provider that can explain exactly what it's waiting for says so
        # itself (Amazon: affiliate tracking ready, API keys still missing)
        ready = getattr(provider, "ready", None)
        return ConnectionTestOut(ok=False, message=ready if isinstance(ready, str) else str(exc))
    message = f"Live search works ({len(results)} result for “shirt”)."
    if slug == "ebay" and not s.EBAY_CAMPAIGN_ID:
        message += " Commission is NOT being earned: no Partner Network campaign ID set."
    if slug == "amazon" and not s.AMAZON_PARTNER_TAG:
        message += " Commission is NOT being earned: no Associate ID set."
    return ConnectionTestOut(ok=True, message=message)


@router.post("/test/{group}", response_model=ConnectionTestOut)
async def test_connection(group: str, _: AdminUser):
    if group not in _TESTABLE_GROUPS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No connection test for this section")
    await refresh_if_stale(force=True)
    s = get_settings()
    try:
        if group == "ai_tryon":
            result = await _test_fashn(s)
        elif group == "ai_stylist":
            result = await _test_openai(s)
        elif group == "payments":
            result = await _test_stripe(s)
        elif group == "email":
            result = await _test_smtp(s)
        else:
            result = await _test_retailer(group, s)
    except Exception as exc:  # noqa: BLE001 — surface network/provider errors to the admin, not a 500
        result = ConnectionTestOut(ok=False, message=f"Connection failed: {exc}")
    result.message = _redact(result.message, s)
    return result
