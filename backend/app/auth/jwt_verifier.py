"""Asymmetric Supabase JWT verification with bounded JWKS caching."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import jwt

from ..config import settings
from .models import AssuranceLevel


class AccessTokenError(RuntimeError):
    """Raised when a bearer token does not satisfy the verification contract."""


@dataclass(frozen=True)
class VerifiedClaims:
    """Required, verified Supabase access-token claims."""

    auth_user_id: UUID
    session_id: UUID
    assurance_level: AssuranceLevel
    email: str | None


@dataclass(frozen=True)
class McpVerifiedClaims:
    """Verified claims that distinguish an OAuth client from a browser session."""

    auth_user_id: UUID
    client_id: str
    scopes: list[str]
    expires_at: int
    issuer: str


class SupabaseJwtVerifier:
    """Verify project JWTs against cached asymmetric public keys."""

    _cache_seconds = 600

    def __init__(self) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def _load_keys(self, *, force: bool = False) -> None:
        issuer = settings.auth_issuer
        if issuer is None:
            raise AccessTokenError("Authentication is not configured.")
        if (
            not force
            and self._keys
            and time.monotonic() - self._loaded_at < self._cache_seconds
        ):
            return
        async with self._lock:
            if (
                not force
                and self._keys
                and time.monotonic() - self._loaded_at < self._cache_seconds
            ):
                return
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{issuer}/.well-known/jwks.json")
                    response.raise_for_status()
            except httpx.HTTPError as error:
                raise AccessTokenError(
                    "Token verification is temporarily unavailable."
                ) from error
            payload = response.json()
            keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(keys, list):
                raise AccessTokenError(
                    "The identity provider returned invalid signing keys."
                )
            self._keys = {
                str(key["kid"]): key
                for key in keys
                if isinstance(key, dict) and isinstance(key.get("kid"), str)
            }
            self._loaded_at = time.monotonic()

    async def _decode(
        self,
        token: str,
        *,
        audience: str,
        required_claims: list[str],
    ) -> dict[str, Any]:
        """Verify a project JWT and return its trusted claims."""
        issuer = settings.auth_issuer
        if issuer is None:
            raise AccessTokenError("Authentication is not configured.")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise AccessTokenError("Invalid access token.") from error
        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in settings.supabase_jwt_algorithms or not isinstance(
            key_id, str
        ):
            raise AccessTokenError("Unsupported access token.")
        await self._load_keys()
        key_data = self._keys.get(key_id)
        if key_data is None:
            await self._load_keys(force=True)
            key_data = self._keys.get(key_id)
        if key_data is None:
            raise AccessTokenError("Unknown access-token signing key.")
        try:
            public_key = jwt.PyJWK.from_dict(key_data, algorithm=algorithm).key
            claims: dict[str, Any] = jwt.decode(
                token,
                public_key,
                algorithms=[algorithm],
                audience=audience,
                issuer=issuer,
                leeway=30,
                options={"require": required_claims},
            )
            if claims.get("role") != "authenticated":
                raise AccessTokenError("The token is not an authenticated user token.")
            return claims
        except AccessTokenError:
            raise
        except (jwt.PyJWTError, ValueError, KeyError) as error:
            raise AccessTokenError("Invalid or expired access token.") from error

    async def verify(self, token: str) -> VerifiedClaims:
        """Verify signature and required browser identity/session claims."""
        claims = await self._decode(
            token,
            audience=settings.supabase_jwt_audience,
            required_claims=[
                "aud",
                "exp",
                "iat",
                "iss",
                "role",
                "session_id",
                "sub",
            ],
        )
        try:
            return VerifiedClaims(
                auth_user_id=UUID(str(claims["sub"])),
                session_id=UUID(str(claims["session_id"])),
                assurance_level=AssuranceLevel(str(claims.get("aal", "aal1"))),
                email=claims.get("email")
                if isinstance(claims.get("email"), str)
                else None,
            )
        except (ValueError, KeyError) as error:
            raise AccessTokenError("Invalid or expired access token.") from error

    async def verify_mcp(self, token: str) -> McpVerifiedClaims:
        """Verify a Supabase OAuth access token intended for MCP."""
        claims = await self._decode(
            token,
            audience=settings.mcp_oauth_audience,
            required_claims=[
                "aud",
                "client_id",
                "exp",
                "iat",
                "iss",
                "role",
                "sub",
            ],
        )
        client_id = claims.get("client_id")
        if not isinstance(client_id, str) or not client_id.strip():
            raise AccessTokenError("The token was not issued to an OAuth client.")
        raw_scope = claims.get("scope", "")
        if isinstance(raw_scope, str):
            scopes = raw_scope.split()
        elif isinstance(raw_scope, list) and all(
            isinstance(scope, str) for scope in raw_scope
        ):
            scopes = raw_scope
        else:
            scopes = []
        try:
            return McpVerifiedClaims(
                auth_user_id=UUID(str(claims["sub"])),
                client_id=client_id,
                scopes=scopes,
                expires_at=int(claims["exp"]),
                issuer=str(claims["iss"]),
            )
        except (TypeError, ValueError, KeyError) as error:
            raise AccessTokenError("Invalid or expired access token.") from error


jwt_verifier = SupabaseJwtVerifier()
