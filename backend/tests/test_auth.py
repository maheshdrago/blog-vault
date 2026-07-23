"""Authentication boundary tests that do not call the external identity provider."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_principal
from backend.app.auth.jwt_verifier import AccessTokenError, SupabaseJwtVerifier
from backend.app.auth.models import (
    AppRole,
    AssuranceLevel,
    AuthenticatedPrincipal,
    OAuthStartInput,
    is_safe_auth_return_path,
)
from backend.app.auth.provider import ProviderUser
from backend.app.auth.repository import AuthRepository
from backend.app.auth.routes import _clear_auth_cookies, _set_auth_cookies
from backend.app.config import settings
from backend.app.database import get_database_session
from backend.app.main import app


def test_first_profile_claims_legacy_vault_atomically() -> None:
    """The first authenticated profile claims both unowned content roots."""
    session_mock = AsyncMock()
    session_mock.add = MagicMock()
    session_mock.scalar.side_effect = [None, None]
    repository = AuthRepository(cast(AsyncSession, session_mock))
    auth_user_id = uuid4()
    user = ProviderUser(
        user_id=str(auth_user_id),
        email="owner@example.com",
        metadata={"display_name": "Owner"},
    )

    profile = asyncio.run(repository.ensure_profile(user))

    assert profile.auth_user_id == auth_user_id
    assert profile.display_name == "Owner"
    assert session_mock.execute.await_count == 3
    statements = [str(call.args[0]) for call in session_mock.execute.await_args_list]
    assert "pg_advisory_xact_lock" in statements[0]
    assert statements[1].startswith("UPDATE articles")
    assert statements[2].startswith("UPDATE learning_paths")
    session_mock.flush.assert_awaited_once()


def test_jwt_verifier_requires_signed_identity_and_session_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A correctly signed project JWT should produce typed identity claims."""
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    issuer = "https://example.supabase.co/auth/v1"
    monkeypatch.setattr(settings, "supabase_jwt_issuer", issuer)
    now = datetime.now(UTC)
    auth_user_id = uuid4()
    session_id = uuid4()
    token = jwt.encode(
        {
            "aud": "authenticated",
            "exp": now + timedelta(minutes=30),
            "iat": now,
            "iss": issuer,
            "role": "authenticated",
            "sub": str(auth_user_id),
            "session_id": str(session_id),
            "aal": "aal1",
            "email": "reader@example.com",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    verifier = SupabaseJwtVerifier()
    verifier._keys = {"test-key": public_jwk}
    verifier._loaded_at = time.monotonic()

    claims = asyncio.run(verifier.verify(token))

    assert claims.auth_user_id == auth_user_id
    assert claims.session_id == session_id
    assert claims.email == "reader@example.com"


def test_jwt_verifier_rejects_unapproved_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsigned or symmetric tokens must never enter the JWKS verification path."""
    monkeypatch.setattr(
        settings, "supabase_jwt_issuer", "https://example.supabase.co/auth/v1"
    )
    token = jwt.encode({"sub": str(uuid4())}, "x" * 32, algorithm="HS256")

    with pytest.raises(AccessTokenError, match="Unsupported"):
        asyncio.run(SupabaseJwtVerifier().verify(token))


def test_jwt_verifier_accepts_only_oauth_tokens_at_mcp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MCP JWT verification requires the OAuth-only client_id claim."""
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2_048)
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk.update({"kid": "oauth-key", "alg": "RS256", "use": "sig"})
    issuer = "https://example.supabase.co/auth/v1"
    monkeypatch.setattr(settings, "supabase_jwt_issuer", issuer)
    now = datetime.now(UTC)
    base_claims = {
        "aud": "authenticated",
        "exp": now + timedelta(minutes=30),
        "iat": now,
        "iss": issuer,
        "role": "authenticated",
        "sub": str(uuid4()),
    }
    verifier = SupabaseJwtVerifier()
    verifier._keys = {"oauth-key": public_jwk}
    verifier._loaded_at = time.monotonic()
    oauth_token = jwt.encode(
        {**base_claims, "client_id": str(uuid4()), "scope": "openid email"},
        private_key,
        algorithm="RS256",
        headers={"kid": "oauth-key"},
    )
    browser_token = jwt.encode(
        base_claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "oauth-key"},
    )

    claims = asyncio.run(verifier.verify_mcp(oauth_token))

    assert claims.scopes == ["openid", "email"]
    with pytest.raises(AccessTokenError, match="Invalid"):
        asyncio.run(verifier.verify_mcp(browser_token))


def test_auth_return_paths_preserve_only_uuid_consent_requests() -> None:
    """Authentication redirects cannot be turned into an open redirect."""
    authorization_id = uuid4()
    consent_path = f"/oauth/consent?authorization_id={authorization_id}"

    assert is_safe_auth_return_path(consent_path)
    assert OAuthStartInput(provider="github", return_to=consent_path).return_to == (
        consent_path
    )
    assert not is_safe_auth_return_path("https://attacker.example/callback")
    assert not is_safe_auth_return_path("/oauth/consent?authorization_id=bad")


def test_auth_cookie_is_http_only_secure_and_host_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production refresh credentials should receive the complete cookie policy."""
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    response = Response()

    _set_auth_cookies(response, "refresh-secret", "csrf-value")

    cookies = response.headers.getlist("set-cookie")
    refresh = next(value for value in cookies if "__Host-blog_refresh" in value)
    csrf = next(value for value in cookies if "blog_csrf" in value)
    assert "HttpOnly" in refresh
    assert "Secure" in refresh
    assert "SameSite=lax" in refresh
    assert "Path=/" in refresh
    assert "Domain=" not in refresh
    assert "HttpOnly" not in csrf

    cleared = Response()
    _clear_auth_cookies(cleared)
    assert any(
        "__Host-blog_refresh" in value
        for value in cleared.headers.getlist("set-cookie")
    )


def test_me_endpoint_rejects_missing_bearer_before_repository_access() -> None:
    """Personal endpoints must not accept a browser-selected owner identifier."""

    async def fake_database_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, object())

    app.dependency_overrides[get_database_session] = fake_database_session
    try:
        response = TestClient(app).get("/api/v1/me/preferences")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_article_catalog_requires_authentication() -> None:
    """Signed-out callers cannot discover article metadata or bodies."""

    async def fake_database_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, object())

    app.dependency_overrides[get_database_session] = fake_database_session
    try:
        response = TestClient(app).get("/api/v1/me/posts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert TestClient(app).get("/api/v1/posts").status_code == 404


def test_sign_in_rejects_unknown_origin_before_provider_call() -> None:
    """Credential submission from an unapproved browser origin is denied."""

    async def fake_database_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, object())

    app.dependency_overrides[get_database_session] = fake_database_session
    try:
        response = TestClient(app).post(
            "/api/v1/auth/sign-in",
            headers={"Origin": "https://attacker.example"},
            json={"email": "reader@example.com", "password": "password123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_oauth_consent_details_are_bound_to_authenticated_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The consent BFF returns only a request for the current account."""
    auth_user_id = uuid4()
    authorization_id = uuid4()

    async def authenticated_reader() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            auth_user_id=auth_user_id,
            reader_id=uuid4(),
            session_id=uuid4(),
            role=AppRole.READER,
            assurance_level=AssuranceLevel.AAL1,
            email="reader@example.com",
        )

    details = AsyncMock(
        return_value={
            "authorization_id": str(authorization_id),
            "redirect_uri": "https://client.example/callback",
            "client": {
                "id": str(uuid4()),
                "name": "Test Client",
                "uri": "https://client.example",
                "logo_uri": "",
            },
            "user": {
                "id": str(auth_user_id),
                "email": "reader@example.com",
            },
            "scope": "openid email",
        }
    )
    monkeypatch.setattr(
        "backend.app.auth.routes.supabase_auth.oauth_authorization_details",
        details,
    )
    app.dependency_overrides[require_principal] = authenticated_reader
    try:
        response = TestClient(app).get(
            f"/api/v1/auth/oauth/authorizations/{authorization_id}",
            headers={"Authorization": "Bearer provider-access"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["client"]["name"] == "Test Client"
    details.assert_awaited_once_with(
        str(authorization_id), "provider-access"
    )


def test_oauth_consent_decision_requires_allowed_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A foreign site cannot drive a signed-in user's consent decision."""

    async def authenticated_reader() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            auth_user_id=uuid4(),
            reader_id=uuid4(),
            session_id=uuid4(),
            role=AppRole.READER,
            assurance_level=AssuranceLevel.AAL1,
            email="reader@example.com",
        )

    decision = AsyncMock(
        return_value={"redirect_url": "https://client.example/callback?code=abc"}
    )
    monkeypatch.setattr(
        "backend.app.auth.routes.supabase_auth.decide_oauth_authorization",
        decision,
    )
    app.dependency_overrides[require_principal] = authenticated_reader
    try:
        response = TestClient(app).post(
            f"/api/v1/auth/oauth/authorizations/{uuid4()}/consent",
            headers={
                "Authorization": "Bearer provider-access",
                "Origin": "https://attacker.example",
            },
            json={"decision": "approve"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    decision.assert_not_awaited()


def test_legacy_anonymous_reader_endpoint_is_removed() -> None:
    """A random UUID must no longer act as an ownership credential."""
    response = TestClient(app).get(f"/api/v1/readers/{uuid4()}/reading-states")

    assert response.status_code == 404
