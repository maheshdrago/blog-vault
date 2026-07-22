"""Integration tests for public REST endpoints."""

from collections.abc import AsyncIterator, Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_database_session
from backend.app.main import app
from backend.app.review.repository import ReviewRepository
from backend.app.security import require_admin_token


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Run one application lifespan for all API tests."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient) -> None:
    """The health endpoint should report available published content."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "databaseConfigured" in response.json()
    assert "articleReviewConfigured" in response.json()
    assert "telemetryConfigured" in response.json()


def test_mcp_rejects_requests_without_credentials(client: TestClient) -> None:
    """The article-capable MCP endpoint must never allow anonymous access."""
    response = client.post("/mcp/")

    assert response.status_code in {401, 503}


def test_review_dashboard_api_rejects_anonymous_access(client: TestClient) -> None:
    """The human review queue must never be readable without admin access."""
    response = client.get("/api/v1/admin/reviews")

    assert response.status_code in {401, 503}


def test_review_dashboard_api_returns_authenticated_queue(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An authenticated dashboard receives the serialized review queue."""

    async def allow_admin() -> None:
        return None

    async def fake_database_session() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, object())

    include_published_values: list[bool] = []

    async def empty_queue(
        _: ReviewRepository, *, include_published: bool = False
    ) -> list[object]:
        include_published_values.append(include_published)
        return []

    app.dependency_overrides[require_admin_token] = allow_admin
    app.dependency_overrides[get_database_session] = fake_database_session
    monkeypatch.setattr(ReviewRepository, "list_queue", empty_queue)
    try:
        response = client.get("/api/v1/admin/reviews?includePublished=true")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []
    assert include_published_values == [True]
