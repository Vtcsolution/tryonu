from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.core.security import TokenType, decode_token
from app.models.user import User
from app.schemas.common import Message
from app.schemas.user import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth_service, google_oauth

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("auth_register", limit=10, window_seconds=3600))],
)
async def register(payload: RegisterRequest, request: Request, response: Response, db: DbSession):
    user = await auth_service.register_user(
        db, email=payload.email.lower(), password=payload.password, full_name=payload.full_name
    )
    access, refresh = await auth_service.issue_tokens(db, user, user_agent=request.headers.get("user-agent"))
    set_auth_cookies(response, access_token=access, refresh_token=refresh)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limiter("auth_login", limit=20, window_seconds=3600))],
)
async def login(payload: LoginRequest, request: Request, response: Response, db: DbSession):
    user = await auth_service.authenticate_local(db, email=payload.email.lower(), password=payload.password)
    access, refresh = await auth_service.issue_tokens(db, user, user_agent=request.headers.get("user-agent"))
    set_auth_cookies(response, access_token=access, refresh_token=refresh)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: DbSession,
    refresh_token: str | None = Cookie(default=None),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token provided")
    try:
        user_id = decode_token(refresh_token, TokenType.REFRESH)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    access, new_refresh = await auth_service.rotate_refresh_token(db, refresh_token=refresh_token, user_id=user_id)
    user = await db.get(User, user_id)
    set_auth_cookies(response, access_token=access, refresh_token=new_refresh)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/logout", response_model=Message)
async def logout(
    response: Response,
    db: DbSession,
    refresh_token: str | None = Cookie(default=None),
):
    if refresh_token:
        try:
            user_id = decode_token(refresh_token, TokenType.REFRESH)
            await auth_service.revoke_refresh_token(db, refresh_token=refresh_token, user_id=user_id)
        except Exception:  # noqa: BLE001 — logout must always succeed client-side
            pass
    clear_auth_cookies(response)
    return Message(detail="Logged out")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return UserOut.model_validate(user)


@router.post(
    "/forgot-password",
    response_model=Message,
    dependencies=[Depends(rate_limiter("auth_forgot_password", limit=5, window_seconds=3600))],
)
async def forgot_password(payload: ForgotPasswordRequest, db: DbSession):
    await auth_service.request_password_reset(db, email=payload.email.lower())
    # Same response whether or not the email exists — never confirm/deny
    # which addresses are registered.
    return Message(detail="If that email is registered, a reset link has been sent.")


@router.post(
    "/reset-password",
    response_model=Message,
    dependencies=[Depends(rate_limiter("auth_reset_password", limit=10, window_seconds=3600))],
)
async def reset_password(payload: ResetPasswordRequest, db: DbSession):
    await auth_service.reset_password(db, token=payload.token, new_password=payload.new_password)
    return Message(detail="Password updated — please sign in again.")


@router.get("/google/login")
async def google_login():
    url = google_oauth.build_authorize_url()
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str, db: DbSession):
    profile = await google_oauth.exchange_code_for_profile(code)

    user = await auth_service.find_or_create_google_user(
        db,
        google_sub=profile.sub,
        email=profile.email.lower(),
        full_name=profile.name,
        avatar_url=profile.picture,
    )
    access, refresh = await auth_service.issue_tokens(db, user)

    redirect = RedirectResponse(f"{settings.FRONTEND_URL}/try")
    set_auth_cookies(redirect, access_token=access, refresh_token=refresh)
    return redirect
