"""Create (or reset) the admin account and a company-store test account, and
print their sign-in details. Run on the server:

    python -m app.scripts.create_accounts

Each run sets a fresh random password for both accounts. Passwords are
printed only on this terminal, never logged or stored in plain text.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import AuthProvider
from app.models.user import User

SITE = "https://tryonu.app"


def new_password() -> str:
    return secrets.token_urlsafe(10)


async def ensure_account(db: AsyncSession, *, email: str, admin: bool, full_name: str) -> str:
    """The account exists, can sign in with a new password, and is (not) admin."""
    password = new_password()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, full_name=full_name, auth_provider=AuthProvider.LOCAL)
        db.add(user)
    user.hashed_password = hash_password(password)
    user.is_admin = admin
    user.is_active = True
    user.email_verified = True
    await db.commit()
    return password


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-email", default="ranazia943@gmail.com")
    parser.add_argument("--store-email", default="ranazia943+store@gmail.com")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        admin_pw = await ensure_account(db, email=args.admin_email.lower(), admin=True, full_name="Admin")
        store_pw = await ensure_account(db, email=args.store_email.lower(), admin=False, full_name="Test Store")

    print()
    print("ADMIN PANEL")
    print(f"  link:     {SITE}/admin")
    print(f"  email:    {args.admin_email.lower()}")
    print(f"  password: {admin_pw}")
    print()
    print("COMPANY STORE PANEL")
    print(f"  link:     {SITE}/business")
    print(f"  email:    {args.store_email.lower()}")
    print(f"  password: {store_pw}")
    print()
    print("Save these now. Running this again gives both accounts new passwords.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
