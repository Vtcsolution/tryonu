from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.email.templates import site_url
from app.core.config import get_settings
from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limiter
from app.core.security import TokenType, decode_token
from app.models.user import User
from app.schemas.common import Message
from app.schemas.user import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
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
        db, email=payload.email.lower(), password=payload.password, full_name=payload.full_name, next_path=payload.next
    )
    if payload.country:
        from app.models.preference import UserPreference

        db.add(UserPreference(user_id=user.id, country=payload.country.upper()))
        await db.commit()
    access, refresh = await auth_service.issue_tokens(db, user, user_agent=request.headers.get("user-agent"))
    set_auth_cookies(response, access_token=access, refresh_token=refresh)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.get("/country-hint")
async def country_hint(request: Request) -> dict[str, str | None]:
    """The visitor's likely country (from the IP), to pre-fill the sign-up form.
    Only a suggestion: the shopper picks their country themselves."""
    from app.services.analytics_service import country_for_request

    return {"country": country_for_request(request)}


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


@router.post(
    "/change-password",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limiter("auth_change_password", limit=10, window_seconds=3600))],
)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, request: Request, response: Response, db: DbSession
):
    await auth_service.change_password(
        db, user=user, current_password=payload.current_password, new_password=payload.new_password
    )
    # other devices are signed out; this one stays signed in with fresh tokens
    access, refresh = await auth_service.issue_tokens(db, user, user_agent=request.headers.get("user-agent"))
    set_auth_cookies(response, access_token=access, refresh_token=refresh)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post(
    "/verify-email",
    response_model=Message,
    dependencies=[Depends(rate_limiter("auth_verify_email", limit=10, window_seconds=3600))],
)
async def verify_email(payload: VerifyEmailRequest, db: DbSession):
    await auth_service.verify_email(db, token=payload.token)
    return Message(detail="Email verified. Thank you!")


@router.post(
    "/resend-verification",
    response_model=Message,
    dependencies=[Depends(rate_limiter("auth_resend_verification", limit=5, window_seconds=3600))],
)
async def resend_verification(user: CurrentUser, db: DbSession):
    await auth_service.resend_verification_email(db, user=user)
    return Message(detail="Verification email sent.")


_OAUTH_COOKIE = "oauth_state"


def _safe_next(next_path: str | None) -> str:
    """Only a page of our own site: "/business", never "//evil.com" or a full URL."""
    if next_path and next_path.startswith("/") and not next_path.startswith("//") and "\\" not in next_path:
        return next_path[:300]
    return "/try"


@router.get("/google/enabled")
async def google_enabled() -> dict[str, bool]:
    """Whether "Continue with Google" is set up, so the website shows the button only then."""
    return {"enabled": google_oauth.is_configured()}


@router.get("/google/login")
async def google_login(next: str | None = None):  # noqa: A002 - the query parameter's name
    import secrets

    state = secrets.token_urlsafe(24)
    url = google_oauth.build_authorize_url(state)
    redirect = RedirectResponse(url)
    # the state comes back from Google and must match this cookie: a sign-in
    # someone else started can't be completed in this browser (login CSRF)
    redirect.set_cookie(
        _OAUTH_COOKIE,
        f"{state}|{_safe_next(next)}",
        max_age=600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/api/v1/auth/google",
    )
    return redirect


@router.get("/google/callback")
async def google_callback(
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    oauth_state: str | None = Cookie(default=None),
):
    expected, _, next_path = (oauth_state or "").partition("|")
    if not code or not state or not expected or state != expected:
        failed = RedirectResponse(site_url("/sign-in?error=google"))
        failed.delete_cookie(_OAUTH_COOKIE, path="/api/v1/auth/google")
        return failed
    profile = await google_oauth.exchange_code_for_profile(code)

    user = await auth_service.find_or_create_google_user(
        db,
        google_sub=profile.sub,
        email=profile.email.lower(),
        full_name=profile.name,
        avatar_url=profile.picture,
    )
    access, refresh = await auth_service.issue_tokens(db, user)

    # back to the page they started from; the website asks for their country there if it's missing
    redirect = RedirectResponse(site_url(_safe_next(next_path)))
    redirect.delete_cookie(_OAUTH_COOKIE, path="/api/v1/auth/google")
    set_auth_cookies(redirect, access_token=access, refresh_token=refresh)
    return redirect
