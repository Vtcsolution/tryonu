"""Create (or update) a TryOnU team member: they can sign in, make try-ons
with the credits given here, and publish them as Ready looks at
tryonu.app/team. Run on the server:

    python -m app.scripts.create_team_member --email person@example.com --name "Full Name" --credits 200

A new account gets a random password, printed only on this terminal (never
logged or stored in plain text). An existing account keeps its password unless
--new-password is given. 10 credits = one outfit try-on.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import AuthProvider, CreditReason
from app.models.user import User
from app.services import credit_service

SITE = "https://tryonu.app"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default=None)
    parser.add_argument("--credits", type=int, default=0, help="credits to add now (10 = one outfit try-on)")
    parser.add_argument("--new-password", action="store_true", help="give an existing account a new password")
    parser.add_argument("--remove", action="store_true", help="take the person off the team (the account stays)")
    args = parser.parse_args()
    email = args.email.strip().lower()

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if args.remove:
            if user is None:
                print(f"No account for {email}.")
                return 1
            user.is_team = False
            await db.commit()
            print(f"{email} is no longer a team member.")
            return 0

        password = None
        if user is None:
            password = secrets.token_urlsafe(10)
            user = User(email=email, full_name=args.name, auth_provider=AuthProvider.LOCAL, email_verified=True)
            user.hashed_password = hash_password(password)
            db.add(user)
            await db.flush()
        elif args.new_password:
            password = secrets.token_urlsafe(10)
            user.hashed_password = hash_password(password)
        if args.name:
            user.full_name = args.name
        user.is_team = True
        user.is_active = True
        if args.credits > 0:
            await credit_service.grant(
                db, user_id=user.id, amount=args.credits, reason=CreditReason.ADMIN_ADJUSTMENT,
                reference_type="user", reference_id=user.id, note="Team member credits",
            )
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)

    print("")
    print("TryOnU team member")
    print(f"  sign in:  {SITE}/sign-in")
    print(f"  email:    {email}")
    print(f"  password: {password if password else '(unchanged: use their current password)'}")
    print(f"  credits:  {balance}  (10 = one outfit try-on)")
    print(f"  panel:    {SITE}/team")
    if password:
        print("")
        print("Send this password privately. They can change it in Settings after signing in.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
