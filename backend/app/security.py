"""Identity helpers shared by private service endpoints."""

from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token


def current_mcp_reader_id() -> UUID:
    """Return the vault owner authenticated for the current MCP request."""
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        raise RuntimeError("MCP vault ownership is unavailable.")
    try:
        return UUID(access_token.subject)
    except ValueError as error:
        raise RuntimeError("MCP vault ownership is invalid.") from error
