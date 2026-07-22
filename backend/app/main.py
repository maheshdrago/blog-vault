"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.learning_path_routes import router as learning_path_router
from .api.review_routes import router as review_router
from .api.routes import router
from .config import settings
from .mcp.server import mcp
from .security import McpBearerAuthMiddleware
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
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Accept", "Authorization", "Content-Type", "X-API-Key"],
        expose_headers=["Mcp-Session-Id"],
    )
    application.include_router(router)
    application.include_router(learning_path_router)
    application.include_router(review_router)
    application.mount(
        "/mcp",
        McpBearerAuthMiddleware(mcp.streamable_http_app()),
        name="mcp",
    )

    distribution = settings.project_root / "dist"
    if distribution.is_dir():
        application.mount(
            "/", StaticFiles(directory=distribution, html=True), name="frontend"
        )
    return application


app = create_app()
