from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.security import verify_password
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.scripts.create_accounts import ensure_account


async def test_creates_admin_and_store_accounts_that_can_sign_in():
    admin_email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    store_email = f"store-{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncSessionLocal() as db:
        admin_pw = await ensure_account(db, email=admin_email, admin=True, full_name="Admin")
        store_pw = await ensure_account(db, email=store_email, admin=False, full_name="Test Store")
        admin = (await db.execute(select(User).where(User.email == admin_email))).scalar_one()
        store = (await db.execute(select(User).where(User.email == store_email))).scalar_one()

    assert admin.is_admin and admin.email_verified and admin.is_active
    assert not store.is_admin and store.email_verified
    assert verify_password(admin_pw, admin.hashed_password)
    assert verify_password(store_pw, store.hashed_password)


async def test_running_again_resets_the_password_of_an_existing_account():
    email = f"again-{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncSessionLocal() as db:
        first = await ensure_account(db, email=email, admin=False, full_name="x")
        second = await ensure_account(db, email=email, admin=True, full_name="x")
        users = (await db.execute(select(User).where(User.email == email))).scalars().all()

    assert len(users) == 1 and users[0].is_admin
    assert first != second
    assert verify_password(second, users[0].hashed_password)
    assert not verify_password(first, users[0].hashed_password)
