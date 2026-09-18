"""Shows which try-on engine the server really uses — and why — and can
switch it, without the admin panel.

    python -m app.scripts.tryon_doctor              # report only
    python -m app.scripts.tryon_doctor --use openai # switch to OpenAI image editing
    python -m app.scripts.tryon_doctor --use fashn  # switch back to FASHN

Switching writes the same encrypted admin setting the Settings page does;
running servers pick it up within ~15 seconds. Never prints secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx
from sqlalchemy import select

from app.core.config import Settings
from app.core.runtime_settings import SettingsValidationError, build_settings, encrypt, load_overrides, validate_value
from app.db.session import AsyncSessionLocal
from app.models.app_setting import AppSetting
from app.models.tryon import TryOnJob


def _yes(value: object) -> str:
    return "set" if value else "NOT SET"


async def _set_provider(value: str) -> None:
    validate_value("VIRTUAL_TRYON_PROVIDER", value)
    current, _ = await load_overrides()
    effective = build_settings(current | {"VIRTUAL_TRYON_PROVIDER": value})
    if effective.VIRTUAL_TRYON_PROVIDER != value:
        key = "OPENAI_API_KEY" if value == "openai" else "FASHN_API_KEY"
        raise SettingsValidationError(f"{key} is not set, so '{value}' would fall back to mock. Add the key first.")
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(select(AppSetting).where(AppSetting.key == "VIRTUAL_TRYON_PROVIDER"))
        ).scalar_one_or_none()
        if row is None:
            session.add(AppSetting(key="VIRTUAL_TRYON_PROVIDER", value_encrypted=encrypt(value)))
        else:
            row.value_encrypted = encrypt(value)
        await session.commit()
    print(f"-> Try-on provider set to '{value}'. Running servers switch within ~15 seconds.\n")


async def _openai_image_access(s: Settings) -> str:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"https://api.openai.com/v1/models/{s.OPENAI_IMAGE_MODEL}",
                headers={"Authorization": f"Bearer {s.OPENAI_API_KEY}"},
            )
    except httpx.RequestError as exc:
        return f"could not reach OpenAI ({exc.__class__.__name__})"
    if resp.status_code == 200:
        return f"OK — this key can use {s.OPENAI_IMAGE_MODEL}"
    try:
        message = resp.json().get("error", {}).get("message", "")
    except ValueError:
        message = ""
    return f"NO ({resp.status_code}) {message[:200]}"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use", choices=["openai", "fashn", "mock"])
    args = parser.parse_args()

    if args.use:
        try:
            await _set_provider(args.use)
        except SettingsValidationError as exc:
            print(f"Not changed: {exc}")
            return 1

    env_only = Settings()
    overrides, _ = await load_overrides()
    effective = build_settings(overrides)

    print("Try-on engine")
    print(f"  .env value                 : {env_only.VIRTUAL_TRYON_PROVIDER}")
    print(f"  admin setting              : {overrides.get('VIRTUAL_TRYON_PROVIDER', '(none — .env value used)')}")
    print(f"  IN USE NOW                 : {effective.VIRTUAL_TRYON_PROVIDER}")
    if overrides.get("VIRTUAL_TRYON_PROVIDER") == "openai" and effective.VIRTUAL_TRYON_PROVIDER != "openai":
        print("  !! 'openai' is chosen but no OpenAI API key is set, so it falls back to mock")
    print(f"  FASHN model                : {effective.FASHN_MODEL}  (key {_yes(effective.FASHN_API_KEY)})")
    print(f"  OpenAI image model         : {effective.OPENAI_IMAGE_MODEL}  (key {_yes(effective.OPENAI_API_KEY)})")
    if effective.OPENAI_API_KEY:
        print(f"  OpenAI image access        : {await _openai_image_access(effective)}")

    async with AsyncSessionLocal() as session:
        jobs = (await session.execute(select(TryOnJob).order_by(TryOnJob.created_at.desc()).limit(5))).scalars().all()
    print("\nLast try-ons (newest first)")
    for job in jobs:
        error = f" — {job.error_message[:120]}" if job.error_message else ""
        print(f"  {job.created_at:%Y-%m-%d %H:%M}  {job.provider}/{job.provider_model}  {job.status.value}{error}")
    if not jobs:
        print("  (none)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
