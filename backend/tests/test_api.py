"""Integration tests for health and protected service endpoints."""

from collections.abc import AsyncIterator, Iterator
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_principal
from backend.app.auth.models import (
    AppRole,
    AssuranceLevel,
    AuthenticatedPrincipal,
)
from backend.app.config import settings
from backend.app.database import get_database_session
from backend.app.main import app
from backend.app.review.repository import ReviewRepository


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Run one application lifespan for all API tests."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient) -> None:
    """The health endpoint should report service configuration safely."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "databaseConfigured" in response.json()
    assert "telemetryConfigured" in response.json()


def test_mcp_rejects_requests_without_credentials(client: TestClient) -> None:
    """The article-capable MCP endpoint must never allow anonymous access."""
    response = client.post("/mcp/")

    assert response.status_code in {401, 503}


def test_mcp_advertises_supabase_oauth_discovery(client: TestClient) -> None:
    """The RFC 9728 document should bind the MCP resource to its OAuth issuer."""
    response = client.get("/.well-known/oauth-protected-resource/mcp/")

    assert response.status_code == 200
    assert response.json() == {
        "resource": settings.mcp_resource_url,
        "authorization_servers": [settings.mcp_oauth_issuer],
        "bearer_methods_supported": ["header"],
    }


def test_review_dashboard_api_rejects_anonymous_access(client: TestClient) -> None:
    """The private review queue must never be readable without an account."""
    response = client.get("/api/v1/me/reviews")

    assert response.status_code in {401, 503}


def test_review_dashboard_api_returns_authenticated_queue(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An authenticated dashboard receives the serialized review queue."""

    reader_id = uuid4()

    async def authenticated_reader() -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            auth_user_id=uuid4(),
            reader_id=reader_id,
            session_id=uuid4(),
            role=AppRole.READER,
            assurance_level=AssuranceLevel.AAL1,
            email="reader@example.com",
        )

    async def fake_database_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, object())

    include_published_values: list[bool] = []

    async def empty_queue(
        _: ReviewRepository, *, include_published: bool = False
    ) -> list[object]:
        include_published_values.append(include_published)
        return []

    app.dependency_overrides[require_principal] = authenticated_reader
    app.dependency_overrides[get_database_session] = fake_database_session
    monkeypatch.setattr(ReviewRepository, "list_queue", empty_queue)
    try:
        response = client.get("/api/v1/me/reviews?includePublished=true")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []
    assert include_published_values == [True]
