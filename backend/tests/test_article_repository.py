"""Unit tests for bounded article persistence and normalization."""

import asyncio
from datetime import UTC, date, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.articles.repository import ArticleRepository
from backend.app.articles.sanitizer import sanitize_article_html
from backend.app.models import ArticleWorkflowStatus, PostInput
from backend.app.tables import ArticleSnapshotTable, ArticleTable


def make_post(html: str) -> PostInput:
    """Return a valid article input with customizable semantic HTML."""
    return PostInput(
        title="A careful guide",
        slug="a-careful-guide",
        date=date(2026, 7, 21),
        description="A specific guide used to verify article storage behavior.",
        tags=["systems"],
        html=html,
    )


def make_article(status: ArticleWorkflowStatus) -> ArticleTable:
    """Build a complete transient working article."""
    now = datetime.now(UTC)
    return ArticleTable(
        article_id=uuid4(),
        slug="a-careful-guide",
        status=status.value,
        title="A careful guide",
        publication_date=date(2026, 7, 21),
        description="A specific guide used to verify article review behavior.",
        tags=["systems"],
        cover="/cover.png",
        featured=False,
        reading_html="<p>Reading copy.</p>",
        experience_html="<!doctype html><html><body>Interactive</body></html>",
        research_sources=[],
        content_hash="a" * 64,
        created_at=now,
        updated_at=now,
    )


def test_sanitizer_removes_scripts_and_event_handlers() -> None:
    """Reading HTML must remain inert before it reaches the database."""
    source = '<h2 onclick="bad()">Safe</h2><script>bad()</script><p>Text</p>'

    cleaned = sanitize_article_html(source)

    assert "onclick" not in cleaned
    assert "<script" not in cleaned
    assert "<h2>Safe</h2>" in cleaned


def test_content_hash_changes_when_article_content_changes() -> None:
    """Optimistic review hashes must include the complete article payload."""
    first = ArticleRepository._content_hash(make_post("<p>One</p>"), None, [])
    second = ArticleRepository._content_hash(make_post("<p>Two</p>"), None, [])

    assert first != second


def test_interactive_draft_enters_human_review_with_frozen_hash() -> None:
    """Submission binds human review to the exact working content."""
    article = make_article(ArticleWorkflowStatus.DRAFT)
    session_mock = AsyncMock()
    session_mock.scalar.return_value = article
    repository = ArticleRepository(cast(AsyncSession, session_mock), uuid4())

    result = asyncio.run(
        repository.submit_for_review(article.slug, article.content_hash)
    )

    assert result.status is ArticleWorkflowStatus.IN_REVIEW
    assert article.status == ArticleWorkflowStatus.IN_REVIEW.value
    assert article.review_cycle_id is not None
    assert article.submitted_content_hash == article.content_hash
    session_mock.flush.assert_awaited_once()


def test_restoring_snapshot_discards_untrusted_working_content() -> None:
    """A human discard restores the last-known-good private copy."""
    article = make_article(ArticleWorkflowStatus.CHANGES_REQUESTED)
    article.review_cycle_id = uuid4()
    published_at = datetime.now(UTC)
    snapshot = ArticleSnapshotTable(
        article_id=article.article_id,
        slug=article.slug,
        title="Published title",
        publication_date=date(2026, 7, 20),
        description="The safe published article.",
        tags=["safe"],
        cover="/safe.png",
        featured=True,
        reading_html="<p>Safe copy.</p>",
        research_sources=[],
        content_hash="b" * 64,
        published_at=published_at,
    )

    ArticleRepository._restore_snapshot(article, snapshot)

    assert article.status == ArticleWorkflowStatus.PUBLISHED.value
    assert article.title == "Published title"
    assert article.content_hash == "b" * 64
    assert article.review_cycle_id is None
    assert article.published_at == published_at


def test_vault_reads_use_snapshot_while_working_copy_is_under_review() -> None:
    """Unapproved LLM content must never replace the safe vault article."""
    article = make_article(ArticleWorkflowStatus.IN_REVIEW)
    snapshot = ArticleSnapshotTable(
        article_id=article.article_id,
        slug=article.slug,
        title="Safe vault title",
        publication_date=date(2026, 7, 20),
        description="The private snapshot.",
        tags=["safe"],
        cover="/safe.png",
        featured=False,
        reading_html="<p>Safe copy.</p>",
        research_sources=[],
        content_hash="d" * 64,
        published_at=datetime.now(UTC),
    )

    assert ArticleRepository._public_row(article, snapshot) is snapshot

    article.status = ArticleWorkflowStatus.PUBLISHED.value
    assert ArticleRepository._public_row(article, snapshot) is article
