"""Browser authentication lifecycle backed by Supabase Auth."""

import base64
import hashlib
import secrets
from contextlib import suppress
from typing import Literal, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from ..config import settings
from ..database import DatabaseSession
from .dependencies import Principal, bearer_token
from .jwt_verifier import AccessTokenError, jwt_verifier
from .models import (
    AuthSessionResponse,
    MessageResponse,
    OAuthAuthorizationDetails,
    OAuthConsentInput,
    OAuthGrant,
    OAuthRedirect,
    OAuthStartInput,
    OAuthStartResponse,
    PasswordResetInput,
    PasswordUpdateInput,
    SignInInput,
    SignUpInput,
    UserSession,
    is_safe_auth_return_path,
)
from .provider import IdentityProviderError, ProviderSession, supabase_auth
from .repository import AuthRepository, SessionRejectedError

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

REFRESH_COOKIE_SECURE = "__Host-blog_refresh"
REFRESH_COOKIE_LOCAL = "blog_refresh"
CSRF_COOKIE = "blog_csrf"
OAUTH_STATE_COOKIE = "blog_oauth_state"
OAUTH_VERIFIER_COOKIE = "blog_oauth_verifier"
OAUTH_RETURN_COOKIE = "blog_oauth_return"


def _refresh_cookie_name() -> str:
    return (
        REFRESH_COOKIE_SECURE if settings.auth_cookie_secure else REFRESH_COOKIE_LOCAL
    )


def _same_site() -> Literal["lax", "strict", "none"]:
    """Narrow validated cookie configuration for Starlette's type contract."""
    return cast(Literal["lax", "strict", "none"], settings.auth_cookie_samesite)


def _set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    max_age = settings.auth_absolute_days * 24 * 60 * 60
    response.set_cookie(
        _refresh_cookie_name(),
        refresh_token,
        max_age=max_age,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=_same_site(),
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        secure=settings.auth_cookie_secure,
        httponly=False,
        samesite=_same_site(),
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    for name in (_refresh_cookie_name(), CSRF_COOKIE):
        response.delete_cookie(
            name,
            secure=settings.auth_cookie_secure,
            httponly=name != CSRF_COOKIE,
            samesite=_same_site(),
            path="/",
        )


def _require_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin not in settings.auth_allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The request origin is not allowed.",
        )


def _require_double_submit_csrf(request: Request, csrf_header: str | None) -> str:
    _require_origin(request)
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    if (
        not csrf_cookie
        or not csrf_header
        or not secrets.compare_digest(csrf_cookie, csrf_header)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed.",
        )
    return csrf_header


def _pkce_values() -> tuple[str, str, str]:
    """Create state, verifier, and RFC 7636 S256 challenge values."""
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return state, verifier, challenge


def _set_pkce_cookies(
    response: Response, *, state: str, verifier: str, return_to: str
) -> None:
    """Retain PKCE correlation data outside JavaScript for one hour."""
    for name, value in (
        (OAUTH_STATE_COOKIE, state),
        (OAUTH_VERIFIER_COOKIE, verifier),
        (OAUTH_RETURN_COOKIE, return_to),
    ):
        response.set_cookie(
            name,
            value,
            max_age=3_600,
            secure=settings.auth_cookie_secure,
            httponly=True,
            samesite=_same_site(),
            path="/",
        )


def _translate_provider(error: IdentityProviderError) -> HTTPException:
    status_code = error.status_code
    if status_code not in {400, 401, 403, 422, 429, 503}:
        status_code = 401
    return HTTPException(status_code=status_code, detail=str(error))


async def _accept_session(
    provider_session: ProviderSession,
    *,
    session: DatabaseSession,
    response: Response,
    user_agent: str | None,
) -> AuthSessionResponse:
    try:
        claims = await jwt_verifier.verify(provider_session.access_token)
    except AccessTokenError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    csrf_token = secrets.token_urlsafe(32)
    repository = AuthRepository(session)
    profile, _ = await repository.register_session(
        claims=claims,
        user=provider_session.user,
        csrf_token=csrf_token,
        user_agent=user_agent,
    )
    principal = await repository.authenticate(claims)
    user = await repository.auth_user(principal)
    _set_auth_cookies(response, provider_session.refresh_token, csrf_token)
    return AuthSessionResponse(
        access_token=provider_session.access_token,
        expires_in=provider_session.expires_in,
        expires_at=provider_session.expires_at,
        user=user,
    )


@router.post("/sign-up", response_model=AuthSessionResponse)
async def sign_up(
    values: SignUpInput,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> AuthSessionResponse:
    """Create an identity while keeping any refresh token out of JavaScript."""
    _require_origin(request)
    state, verifier, challenge = _pkce_values()
    callback = settings.auth_callback_url or str(request.url_for("oauth_callback"))
    redirect_to = f"{callback}?{urlencode({'state': state})}"
    try:
        user, provider_session = await supabase_auth.sign_up(
            values.email,
            values.password,
            values.display_name,
            redirect_to=redirect_to,
            code_challenge=challenge,
        )
    except IdentityProviderError as error:
        raise _translate_provider(error) from error
    if provider_session is None:
        await AuthRepository(session).ensure_profile(user)
        _set_pkce_cookies(
            response,
            state=state,
            verifier=verifier,
            return_to=values.return_to,
        )
        return AuthSessionResponse(
            verification_required=True,
            message="Check your email to verify the account before signing in.",
        )
    return await _accept_session(
        provider_session,
        session=session,
        response=response,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/sign-in", response_model=AuthSessionResponse)
async def sign_in(
    values: SignInInput,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> AuthSessionResponse:
    """Exchange credentials at Supabase and issue browser-safe session state."""
    _require_origin(request)
    try:
        provider_session = await supabase_auth.sign_in(values.email, values.password)
    except IdentityProviderError as error:
        raise _translate_provider(error) from error
    return await _accept_session(
        provider_session,
        session=session,
        response=response,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/oauth/start", response_model=OAuthStartResponse)
async def oauth_start(
    values: OAuthStartInput, request: Request, response: Response
) -> OAuthStartResponse:
    """Create provider state and a PKCE verifier in short-lived HttpOnly cookies."""
    _require_origin(request)
    state, verifier, challenge = _pkce_values()
    callback = settings.auth_callback_url or str(request.url_for("oauth_callback"))
    redirect_to = f"{callback}?{urlencode({'state': state})}"
    authorization_url = supabase_auth.authorization_url(
        provider=values.provider.value,
        redirect_to=redirect_to,
        code_challenge=challenge,
    )
    _set_pkce_cookies(
        response, state=state, verifier=verifier, return_to=values.return_to
    )
    return OAuthStartResponse(authorization_url=authorization_url)


@router.get("/callback", name="oauth_callback")
async def oauth_callback(
    request: Request,
    session: DatabaseSession,
    code: str = Query(min_length=1),
    state: str = Query(min_length=1),
) -> RedirectResponse:
    """Verify OAuth state, exchange the one-time PKCE code, and return home."""
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    verifier = request.cookies.get(OAUTH_VERIFIER_COOKIE)
    if (
        not expected_state
        or not secrets.compare_digest(expected_state, state)
        or not verifier
    ):
        raise HTTPException(
            status_code=400, detail="The OAuth callback state is invalid."
        )
    try:
        provider_session = await supabase_auth.exchange_code(code, verifier)
    except IdentityProviderError as error:
        raise _translate_provider(error) from error
    destination = request.cookies.get(OAUTH_RETURN_COOKIE, "/")
    if not is_safe_auth_return_path(destination):
        destination = "/"
    response = RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
    await _accept_session(
        provider_session,
        session=session,
        response=response,
        user_agent=request.headers.get("user-agent"),
    )
    for name in (OAUTH_STATE_COOKIE, OAUTH_VERIFIER_COOKIE, OAUTH_RETURN_COOKIE):
        response.delete_cookie(name, path="/")
    return response


@router.post("/refresh", response_model=AuthSessionResponse)
async def refresh_session(
    request: Request,
    response: Response,
    session: DatabaseSession,
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> AuthSessionResponse:
    """Rotate the provider refresh token after Origin and CSRF validation."""
    csrf_token = _require_double_submit_csrf(request, csrf_header)
    refresh_token = request.cookies.get(_refresh_cookie_name())
    if not refresh_token:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="No refresh session is available.")
    try:
        provider_session = await supabase_auth.refresh(refresh_token)
        claims = await jwt_verifier.verify(provider_session.access_token)
        repository = AuthRepository(session)
        principal = await repository.authenticate(claims)
        if not await repository.verify_csrf(principal.session_id, csrf_token):
            raise HTTPException(status_code=403, detail="CSRF validation failed.")
        next_csrf = secrets.token_urlsafe(32)
        await repository.rotate_csrf(principal.session_id, next_csrf)
        user = await repository.auth_user(principal)
    except IdentityProviderError as error:
        _clear_auth_cookies(response)
        raise _translate_provider(error) from error
    except (AccessTokenError, SessionRejectedError) as error:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail=str(error)) from error
    _set_auth_cookies(response, provider_session.refresh_token, next_csrf)
    return AuthSessionResponse(
        access_token=provider_session.access_token,
        expires_in=provider_session.expires_in,
        expires_at=provider_session.expires_at,
        user=user,
    )


@router.post("/sign-out", response_model=MessageResponse)
async def sign_out(
    request: Request,
    response: Response,
    principal: Principal,
    session: DatabaseSession,
    authorization: str | None = Header(default=None),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> MessageResponse:
    """Revoke the current provider/application session and clear cookies."""
    csrf_token = _require_double_submit_csrf(request, csrf_header)
    repository = AuthRepository(session)
    if not await repository.verify_csrf(principal.session_id, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")
    with suppress(IdentityProviderError):
        await supabase_auth.sign_out(bearer_token(authorization))
    await repository.revoke_session(principal, principal.session_id)
    await repository.record_event(
        auth_user_id=principal.auth_user_id,
        session_id=principal.session_id,
        event_type="signed_out",
    )
    _clear_auth_cookies(response)
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=AuthSessionResponse)
async def get_me(principal: Principal, session: DatabaseSession) -> AuthSessionResponse:
    """Return the authenticated account without issuing credentials."""
    return AuthSessionResponse(user=await AuthRepository(session).auth_user(principal))


@router.get("/sessions", response_model=list[UserSession])
async def list_sessions(
    principal: Principal, session: DatabaseSession
) -> list[UserSession]:
    """List device sessions belonging to the current account."""
    return await AuthRepository(session).list_sessions(principal)


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: UUID, principal: Principal, session: DatabaseSession
) -> MessageResponse:
    """Immediately revoke one owned application session."""
    if session_id == principal.session_id:
        raise HTTPException(status_code=409, detail="Use sign out for this device.")
    if not await AuthRepository(session).revoke_session(principal, session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return MessageResponse(message="Device session revoked.")


@router.delete("/sessions", response_model=MessageResponse)
async def revoke_other_sessions(
    principal: Principal, session: DatabaseSession
) -> MessageResponse:
    """Immediately revoke every other Blog Vault device session."""
    count = await AuthRepository(session).revoke_other_sessions(principal)
    return MessageResponse(message=f"Revoked {count} other session(s).")


@router.post("/password-reset", response_model=MessageResponse)
async def request_password_reset(
    values: PasswordResetInput, request: Request, response: Response
) -> MessageResponse:
    """Request provider recovery while always returning a generic response."""
    _require_origin(request)
    state, verifier, challenge = _pkce_values()
    callback = settings.auth_callback_url or str(request.url_for("oauth_callback"))
    redirect_to = f"{callback}?{urlencode({'state': state})}"
    with suppress(IdentityProviderError):
        await supabase_auth.request_password_reset(
            values.email.strip().lower(),
            redirect_to=redirect_to,
            code_challenge=challenge,
        )
    _set_pkce_cookies(
        response,
        state=state,
        verifier=verifier,
        return_to="/auth?mode=update",
    )
    return MessageResponse(
        message="If that account exists, password recovery instructions were sent."
    )


@router.post("/update-password", response_model=MessageResponse)
async def update_password(
    values: PasswordUpdateInput,
    principal: Principal,
    authorization: str | None = Header(default=None),
) -> MessageResponse:
    """Update a password through Supabase using a verified active session."""
    try:
        await supabase_auth.update_password(
            bearer_token(authorization), values.password
        )
    except IdentityProviderError as error:
        raise _translate_provider(error) from error
    return MessageResponse(message="Password updated.")


@router.get(
    "/oauth/authorizations/{authorization_id}",
    response_model=OAuthAuthorizationDetails | OAuthRedirect,
)
async def oauth_authorization_details(
    authorization_id: UUID,
    principal: Principal,
    authorization: str | None = Header(default=None),
) -> OAuthAuthorizationDetails | OAuthRedirect:
    """Return trusted client details for the signed-in consent screen."""
    try:
        payload = await supabase_auth.oauth_authorization_details(
            str(authorization_id), bearer_token(authorization)
        )
    except IdentityProviderError as error:
        raise _translate_provider(error) from error
    if "redirect_url" in payload:
        return OAuthRedirect.model_validate(payload)
    details = OAuthAuthorizationDetails.model_validate(payload)
    if details.user.id != principal.auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This authorization request belongs to another account.",
        )
    return details


@router.post(
    "/oauth/authorizations/{authorization_id}/consent",
    response_model=OAuthRedirect,
)
async def decide_oauth_authorization(
    authorization_id: UUID,
    values: OAuthConsentInput,
    request: Request,
    principal: Principal,
    authorization: str | None = Header(default=None),
) -> OAuthRedirect:
    """Apply the user's explicit OAuth approval or denial at Supabase."""
    del principal
    _require_origin(request)
    try:
        payload = await supabase_auth.decide_oauth_authorization(
            str(authorization_id),
            values.decision.value,
            bearer_token(authorization),
        )
    except IdentityProviderError as error:
        raise _translate_provider(error) from error
    return OAuthRedirect.model_validate(payload)


@router.get("/oauth/grants", response_model=list[OAuthGrant])
async def list_oauth_grants(
    principal: Principal,
    authorization: str | None = Header(default=None),
) -> list[OAuthGrant]:
    """List OAuth clients currently authorized by this account."""
    del principal
    try:
        payload = await supabase_auth.list_oauth_grants(
            bearer_token(authorization)
        )
    except IdentityProviderError as error:
        raise _translate_provider(error) from error
    return [OAuthGrant.model_validate(grant) for grant in payload]


@router.delete("/oauth/grants/{client_id}", response_model=MessageResponse)
async def revoke_oauth_grant(
    client_id: UUID,
    request: Request,
    principal: Principal,
    authorization: str | None = Header(default=None),
) -> MessageResponse:
    """Revoke one OAuth client without affecting browser device sessions."""
    del principal
    _require_origin(request)
    try:
        await supabase_auth.revoke_oauth_grant(
            str(client_id), bearer_token(authorization)
        )
    except IdentityProviderError as error:
        raise _translate_provider(error) from error
    return MessageResponse(message="Connector access revoked.")
