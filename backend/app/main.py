"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.me_routes import router as me_router
from .api.review_routes import router as review_router
from .api.routes import router
from .auth.routes import router as auth_router
from .config import settings
from .mcp.server import mcp
from .telemetry import shutdown_telemetry


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start and stop the MCP Streamable HTTP session manager."""
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        shutdown_telemetry()


def create_app() -> FastAPI:
    """Create and configure the Blog Vault ASGI application."""
    application = FastAPI(
        title="Blog Vault API",
        summary="REST and MCP access to an HTML-first personal blog.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-CSRF-Token",
        ],
        expose_headers=["Mcp-Session-Id"],
    )

    @application.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Prevent credential caching and add baseline browser protections."""
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if request.url.path.startswith(("/api/v1/auth", "/api/v1/me")):
            response.headers["Cache-Control"] = "no-store"
        return response

    application.include_router(router)
    application.include_router(auth_router)
    application.include_router(me_router)
    application.include_router(review_router)

    @application.get("/.well-known/oauth-protected-resource/mcp/")
    async def mcp_protected_resource_metadata() -> JSONResponse:
        """Advertise the OAuth issuer for the public MCP resource URL."""
        return JSONResponse(
            {
                "resource": settings.mcp_resource_url,
                "authorization_servers": [settings.mcp_oauth_issuer],
                "bearer_methods_supported": ["header"],
            }
        )

    application.mount("/mcp", mcp.streamable_http_app(), name="mcp")

    distribution = settings.project_root / "dist"
    if distribution.is_dir():
        application.mount(
            "/", StaticFiles(directory=distribution, html=True), name="frontend"
        )
    return application


app = create_app()
