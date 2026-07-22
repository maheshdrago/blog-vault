"""Small ASGI security boundaries for private service endpoints."""

import secrets

from fastapi import Header, HTTPException, status
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import settings


def require_admin_token(
    authorization: str | None = Header(default=None),
) -> None:
    """Require the separate human-review Bearer token for admin routes."""
    expected = settings.admin_access_token
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Article review authentication is not configured.",
        )
    provided = (authorization or "").removeprefix("Bearer ")
    if not provided or not secrets.compare_digest(
        provided, expected.get_secret_value()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


class McpBearerAuthMiddleware:
    """Require a configured Bearer token for every MCP HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an ASGI MCP application."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Authenticate HTTP requests while preserving ASGI lifespan events."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        expected = settings.mcp_access_token
        if expected is None:
            response = JSONResponse(
                {"detail": "MCP authentication is not configured."},
                status_code=503,
            )
            await response(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode()
        provided = authorization.removeprefix("Bearer ")
        if not provided or not secrets.compare_digest(
            provided, expected.get_secret_value()
        ):
            response = JSONResponse(
                {"detail": "Invalid MCP Bearer token."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)
