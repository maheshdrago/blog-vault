"""MCP bearer-token verification for OAuth clients and personal credentials."""

from datetime import UTC, datetime, timedelta

from mcp.server.auth.provider import AccessToken, TokenVerifier
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..auth.jwt_verifier import AccessTokenError, jwt_verifier
from ..auth.mcp_credentials import MCP_TOKEN_PREFIX, hash_mcp_token
from ..config import settings
from ..database import DatabaseNotConfiguredError, database_session
from ..tables import McpCredentialTable, ReaderProfileTable


class BlogVaultTokenVerifier(TokenVerifier):
    """Resolve either supported credential type to one private vault owner."""

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a bearer token without exposing authentication failures."""
        if token.startswith(MCP_TOKEN_PREFIX):
            return await self._verify_personal_token(token)
        return await self._verify_oauth_token(token)

    async def _verify_personal_token(self, token: str) -> AccessToken | None:
        """Resolve a revocable, hashed personal token."""
        try:
            async with database_session() as session:
                row = await session.scalar(
                    select(McpCredentialTable).where(
                        McpCredentialTable.token_hash == hash_mcp_token(token),
                        McpCredentialTable.revoked_at.is_(None),
                    )
                )
                if row is None:
                    return None
                now = datetime.now(UTC)
                last_used = (
                    row.last_used_at
                    if row.last_used_at is None or row.last_used_at.tzinfo
                    else row.last_used_at.replace(tzinfo=UTC)
                )
                if last_used is None or last_used + timedelta(minutes=5) <= now:
                    row.last_used_at = now
                return AccessToken(
                    token=token,
                    client_id=f"personal:{row.credential_id}",
                    scopes=[],
                    subject=str(row.reader_id),
                    resource=settings.mcp_resource_url,
                    claims={"credential_type": "personal"},
                )
        except (DatabaseNotConfiguredError, SQLAlchemyError):
            return None

    async def _verify_oauth_token(self, token: str) -> AccessToken | None:
        """Verify a Supabase OAuth JWT and map its subject to a reader profile."""
        try:
            claims = await jwt_verifier.verify_mcp(token)
            async with database_session() as session:
                reader_id = await session.scalar(
                    select(ReaderProfileTable.reader_id).where(
                        ReaderProfileTable.auth_user_id == claims.auth_user_id
                    )
                )
            if reader_id is None:
                return None
            return AccessToken(
                token=token,
                client_id=claims.client_id,
                scopes=claims.scopes,
                expires_at=claims.expires_at,
                resource=settings.mcp_resource_url,
                subject=str(reader_id),
                claims={
                    "credential_type": "oauth",
                    "issuer": claims.issuer,
                    "auth_user_id": str(claims.auth_user_id),
                },
            )
        except (AccessTokenError, DatabaseNotConfiguredError, SQLAlchemyError):
            return None


token_verifier = BlogVaultTokenVerifier()
