"""Minimal asynchronous client for Supabase Auth's server-side REST API."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from ..config import settings


class IdentityProviderError(RuntimeError):
    """Safe identity-provider failure suitable for API translation."""

    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ProviderUser:
    """Subset of provider identity data used by Blog Vault."""

    user_id: str
    email: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProviderSession:
    """Supabase token pair retained only for the current request."""

    access_token: str
    refresh_token: str
    expires_in: int
    expires_at: int | None
    user: ProviderUser


class SupabaseAuthClient:
    """Call Supabase Auth without persisting provider credentials."""

    def _configuration(self) -> tuple[str, str]:
        if not settings.auth_configured:
            raise IdentityProviderError(
                "Authentication is not configured.", status_code=503
            )
        assert settings.supabase_url is not None
        assert settings.supabase_publishable_key is not None
        return (
            f"{settings.supabase_url.rstrip('/')}/auth/v1",
            settings.supabase_publishable_key.get_secret_value(),
        )

    async def _request_value(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> Any:
        base_url, api_key = self._configuration()
        headers = {"apikey": api_key, "Accept": "application/json"}
        if access_token is not None:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(
                    method, f"{base_url}{path}", json=body, headers=headers
                )
        except httpx.HTTPError as error:
            raise IdentityProviderError(
                "The identity service is temporarily unavailable.", status_code=503
            ) from error
        if response.is_error:
            detail = "Authentication could not be completed."
            if response.status_code == 429:
                detail = "Too many authentication attempts. Try again later."
            elif response.status_code >= 500:
                detail = "The identity service is temporarily unavailable."
            raise IdentityProviderError(
                detail,
                status_code=503
                if response.status_code >= 500
                else response.status_code,
            )
        if not response.content:
            return {}
        return response.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Return one object-shaped provider response."""
        value = await self._request_value(
            method, path, body=body, access_token=access_token
        )
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _provider_user(payload: dict[str, Any]) -> ProviderUser:
        metadata = payload.get("user_metadata")
        return ProviderUser(
            user_id=str(payload["id"]),
            email=payload.get("email")
            if isinstance(payload.get("email"), str)
            else None,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def _session(self, payload: dict[str, Any]) -> ProviderSession | None:
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        user = payload.get("user")
        if not isinstance(access, str) or not isinstance(refresh, str):
            return None
        if not isinstance(user, dict) or "id" not in user:
            raise IdentityProviderError(
                "The identity response was incomplete.", status_code=503
            )
        return ProviderSession(
            access_token=access,
            refresh_token=refresh,
            expires_in=int(payload.get("expires_in", 1800)),
            expires_at=int(payload["expires_at"])
            if payload.get("expires_at")
            else None,
            user=self._provider_user(user),
        )

    async def sign_up(
        self,
        email: str,
        password: str,
        display_name: str | None,
        *,
        redirect_to: str,
        code_challenge: str,
    ) -> tuple[ProviderUser, ProviderSession | None]:
        body: dict[str, Any] = {
            "email": email,
            "password": password,
            "code_challenge": code_challenge,
            "code_challenge_method": "s256",
        }
        if display_name:
            body["data"] = {"display_name": display_name}
        payload = await self._request(
            "POST", f"/signup?{urlencode({'redirect_to': redirect_to})}", body=body
        )
        user_payload = payload.get("user") or payload
        if not isinstance(user_payload, dict) or "id" not in user_payload:
            raise IdentityProviderError(
                "The identity response was incomplete.", status_code=503
            )
        return self._provider_user(user_payload), self._session(payload)

    async def sign_in(self, email: str, password: str) -> ProviderSession:
        payload = await self._request(
            "POST",
            "/token?grant_type=password",
            body={"email": email, "password": password},
        )
        session = self._session(payload)
        if session is None:
            raise IdentityProviderError("Sign-in did not create a session.")
        return session

    async def refresh(self, refresh_token: str) -> ProviderSession:
        payload = await self._request(
            "POST",
            "/token?grant_type=refresh_token",
            body={"refresh_token": refresh_token},
        )
        session = self._session(payload)
        if session is None:
            raise IdentityProviderError("The session could not be refreshed.")
        return session

    async def exchange_code(self, code: str, verifier: str) -> ProviderSession:
        payload = await self._request(
            "POST",
            "/token?grant_type=pkce",
            body={"auth_code": code, "code_verifier": verifier},
        )
        session = self._session(payload)
        if session is None:
            raise IdentityProviderError("The OAuth session could not be created.")
        return session

    def authorization_url(
        self, *, provider: str, redirect_to: str, code_challenge: str
    ) -> str:
        base_url, _ = self._configuration()
        query = urlencode(
            {
                "provider": provider,
                "redirect_to": redirect_to,
                "code_challenge": code_challenge,
                "code_challenge_method": "s256",
            }
        )
        return f"{base_url}/authorize?{query}"

    async def sign_out(self, access_token: str) -> None:
        await self._request("POST", "/logout?scope=local", access_token=access_token)

    async def request_password_reset(
        self,
        email: str,
        *,
        redirect_to: str,
        code_challenge: str,
    ) -> None:
        body: dict[str, Any] = {
            "email": email,
            "redirect_to": redirect_to,
            "code_challenge": code_challenge,
            "code_challenge_method": "s256",
        }
        await self._request("POST", "/recover", body=body)

    async def update_password(self, access_token: str, password: str) -> None:
        await self._request(
            "PUT", "/user", body={"password": password}, access_token=access_token
        )

    async def oauth_authorization_details(
        self, authorization_id: str, access_token: str
    ) -> dict[str, Any]:
        """Retrieve a provider-validated pending OAuth authorization."""
        return await self._request(
            "GET",
            f"/oauth/authorizations/{authorization_id}",
            access_token=access_token,
        )

    async def decide_oauth_authorization(
        self,
        authorization_id: str,
        decision: str,
        access_token: str,
    ) -> dict[str, Any]:
        """Approve or deny a pending OAuth authorization at Supabase."""
        return await self._request(
            "POST",
            f"/oauth/authorizations/{authorization_id}/consent",
            body={"action": decision},
            access_token=access_token,
        )

    async def list_oauth_grants(self, access_token: str) -> list[dict[str, Any]]:
        """List OAuth grants belonging to the current Supabase user."""
        payload = await self._request_value(
            "GET", "/user/oauth/grants", access_token=access_token
        )
        grants = (
            payload.get("grants", payload.get("data", []))
            if isinstance(payload, dict)
            else payload
        )
        if isinstance(grants, list):
            return [grant for grant in grants if isinstance(grant, dict)]
        return []

    async def revoke_oauth_grant(self, client_id: str, access_token: str) -> None:
        """Revoke the current user's grant for one OAuth client."""
        await self._request(
            "DELETE",
            f"/user/oauth/grants?{urlencode({'client_id': client_id})}",
            access_token=access_token,
        )


supabase_auth = SupabaseAuthClient()
