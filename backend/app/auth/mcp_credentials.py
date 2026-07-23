"""Creation, hashing, and revocation of personal MCP credentials."""

import secrets
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..tables import McpCredentialTable
from .models import (
    AuthenticatedPrincipal,
    McpCredential,
    McpCredentialCreated,
    McpCredentialCreateInput,
)

MCP_TOKEN_PREFIX = "bv_mcp_"


def hash_mcp_token(token: str) -> str:
    """Hash a high-entropy bearer token before lookup or persistence."""
    return sha256(token.encode()).hexdigest()


class McpCredentialRepository:
    """Manage credentials belonging only to one authenticated reader."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, principal: AuthenticatedPrincipal) -> list[McpCredential]:
        """List safe credential metadata without returning token material."""
        rows = await self._session.scalars(
            select(McpCredentialTable)
            .where(McpCredentialTable.reader_id == principal.reader_id)
            .order_by(McpCredentialTable.created_at.desc())
        )
        return [self._to_model(row) for row in rows]

    async def create(
        self,
        principal: AuthenticatedPrincipal,
        values: McpCredentialCreateInput,
    ) -> McpCredentialCreated:
        """Generate one token and persist only its SHA-256 digest."""
        token = f"{MCP_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        row = McpCredentialTable(
            reader_id=principal.reader_id,
            label=values.label,
            token_hash=hash_mcp_token(token),
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return McpCredentialCreated(**self._to_model(row).model_dump(), token=token)

    async def revoke(
        self, principal: AuthenticatedPrincipal, credential_id: UUID
    ) -> bool:
        """Revoke one credential only when the current reader owns it."""
        row = await self._session.get(McpCredentialTable, credential_id)
        if row is None or row.reader_id != principal.reader_id:
            return False
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
        return True

    @staticmethod
    def _to_model(row: McpCredentialTable) -> McpCredential:
        return McpCredential(
            credential_id=row.credential_id,
            label=row.label,
            created_at=row.created_at,
            last_used_at=row.last_used_at,
            revoked_at=row.revoked_at,
        )
