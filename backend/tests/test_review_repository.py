"""Unit tests for the article-based human-review state machine."""

import asyncio
from datetime import UTC, date, datetime
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.articles.repository import ArticleConflictError
from backend.app.models import ArticleWorkflowStatus
from backend.app.review.repository import ReviewRepository
from backend.app.tables import ArticleTable


def make_article(status: ArticleWorkflowStatus) -> ArticleTable:
    """Build a transient working article for state-transition tests."""
    now = datetime.now(UTC)
    return ArticleTable(
        article_id=uuid4(),
        slug="review-workflow",
        status=status.value,
        title="Review workflow",
        publication_date=date(2026, 7, 21),
        description="An article used to verify the human review workflow.",
        tags=["review"],
        cover="/cover.png",
        featured=False,
        reading_html="<p>Review copy.</p>",
        research_sources=[],
        content_hash="b" * 64,
        review_cycle_id=uuid4(),
        submitted_content_hash="b" * 64,
        created_at=now,
        updated_at=now,
    )


def test_approval_rejects_unresolved_feedback() -> None:
    """Human approval must wait until every active thread is resolved."""
    article = make_article(ArticleWorkflowStatus.IN_REVIEW)
    session_mock = AsyncMock()
    session_mock.scalar.side_effect = [article, 1]
    repository = ReviewRepository(cast(AsyncSession, session_mock), uuid4())

    with pytest.raises(ArticleConflictError, match="Resolve every"):
        asyncio.run(repository.approve(article.article_id))


def test_approval_marks_exact_submitted_article_approved() -> None:
    """A clean review approves only the frozen submitted content hash."""
    article = make_article(ArticleWorkflowStatus.IN_REVIEW)
    session_mock = AsyncMock()
    session_mock.scalar.side_effect = [article, 0]
    repository = ReviewRepository(cast(AsyncSession, session_mock), uuid4())
    cast(Any, repository).get_context = AsyncMock(return_value=None)

    asyncio.run(repository.approve(article.article_id))

    assert article.status == ArticleWorkflowStatus.APPROVED.value
    assert article.reviewed_at is not None
    session_mock.flush.assert_awaited_once()


def test_approval_rejects_content_changed_after_submission() -> None:
    """A stale review can never approve content the human did not inspect."""
    article = make_article(ArticleWorkflowStatus.IN_REVIEW)
    article.content_hash = "c" * 64
    session_mock = AsyncMock()
    session_mock.scalar.return_value = article
    repository = ReviewRepository(cast(AsyncSession, session_mock), uuid4())

    with pytest.raises(ArticleConflictError, match="changed after review"):
        asyncio.run(repository.approve(article.article_id))


def test_request_changes_requires_actionable_human_comment() -> None:
    """A reviewer cannot return an article without explaining what should change."""
    article = make_article(ArticleWorkflowStatus.IN_REVIEW)
    session_mock = AsyncMock()
    session_mock.scalar.side_effect = [article, 0]
    repository = ReviewRepository(cast(AsyncSession, session_mock), uuid4())

    with pytest.raises(ArticleConflictError, match="at least one"):
        asyncio.run(repository.request_changes(article.article_id))


def test_request_changes_preserves_cycle_and_unfreezes_content() -> None:
    """Revision requests retain comments while allowing the working copy to change."""
    article = make_article(ArticleWorkflowStatus.IN_REVIEW)
    cycle_id = article.review_cycle_id
    session_mock = AsyncMock()
    session_mock.scalar.side_effect = [article, 1]
    repository = ReviewRepository(cast(AsyncSession, session_mock), uuid4())
    cast(Any, repository).get_context = AsyncMock(return_value=None)

    asyncio.run(repository.request_changes(article.article_id))

    assert article.status == ArticleWorkflowStatus.CHANGES_REQUESTED.value
    assert article.review_cycle_id == cycle_id
    assert article.submitted_content_hash is None
