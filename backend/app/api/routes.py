"""Unauthenticated service-readiness endpoint."""

from fastapi import APIRouter

from ..config import settings
from ..models import HealthResponse

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return service readiness and external integration configuration."""
    return HealthResponse(
        status="ok",
        database_configured=settings.database_url is not None,
        telemetry_configured=settings.langfuse_configured,
        authentication_configured=settings.auth_configured,
    )
