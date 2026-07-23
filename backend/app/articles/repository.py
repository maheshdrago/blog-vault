"""Bounded PostgreSQL persistence for working articles and published snapshots."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ArticleDetail,
    ArticleRecord,
    ArticleSnapshot,
    ArticleWorkflowStatus,
    InteractivePostInput,
    Post,
    PostInput,
    PostSummary,
    ResearchSource,
)
from ..tables import ArticleSnapshotTable, ArticleTable
from .sanitizer import sanitize_article_html


class ArticleNotFoundError(LookupError):
    """Raised when an article is absent from the current private vault."""


class ArticleConflictError(ValueError):
    """Raised when an article operation conflicts with stored workflow state."""


class ArticleRepository:
    """Own one working copy and at most one last-published snapshot per article."""

    def __init__(self, session: AsyncSession, owner_reader_id: UUID) -> None:
        """Bind every repository operation to one authenticated vault owner."""
        self._session = session
        self._owner_reader_id = owner_reader_id

    async def list_published(self) -> list[PostSummary]:
        """Return owner summaries, falling back to snapshots during review."""
        rows = await self._session.execute(
            select(ArticleTable, ArticleSnapshotTable)
            .outerjoin(
                ArticleSnapshotTable,
                ArticleSnapshotTable.article_id == ArticleTable.article_id,
            )
            .where(
                ArticleTable.owner_reader_id == self._owner_reader_id,
                or_(
                    ArticleTable.status == ArticleWorkflowStatus.PUBLISHED.value,
                    ArticleSnapshotTable.article_id.is_not(None),
                ),
            )
        )
        public = [self._public_row(article, snapshot) for article, snapshot in rows]
        public.sort(
            key=lambda row: (row.publication_date, row.published_at), reverse=True
        )
        return [self._summary_for(row) for row in public]

    async def get_published(self, slug: str) -> Post:
        """Return the safe published copy within the owner's vault."""
        return self._to_post(await self._public_content(slug))

    async def get_published_experience(self, slug: str) -> str:
        """Return the owner's published interactive document."""
        row = await self._public_content(slug)
        if row.experience_html is None:
            raise ArticleNotFoundError(f"Interactive experience not found: {slug}")
        return row.experience_html

    async def search_published(self, query: str, limit: int = 10) -> list[Post]:
        """Search the owner's safe published article copies in memory."""
        needle = query.casefold().strip()
        if not needle:
            return []
        rows = await self._session.execute(
            select(ArticleTable, ArticleSnapshotTable)
            .outerjoin(
                ArticleSnapshotTable,
                ArticleSnapshotTable.article_id == ArticleTable.article_id,
            )
            .where(ArticleTable.owner_reader_id == self._owner_reader_id)
        )
        matches: list[Post] = []
        for article, snapshot in rows:
            if (
                article.status != ArticleWorkflowStatus.PUBLISHED.value
                and snapshot is None
            ):
                continue
            row = self._public_row(article, snapshot)
            searchable = " ".join(
                [row.title, row.description, *row.tags, row.reading_html]
            ).casefold()
            if needle in searchable:
                matches.append(self._to_post(row))
            if len(matches) >= min(max(limit, 1), 20):
                break
        return matches

    async def create_draft(
        self,
        values: PostInput | InteractivePostInput,
        revision_notes: str | None = None,
    ) -> ArticleDetail:
        """Create the single working copy for a new article."""
        if await self._article_by_slug(values.slug) is not None:
            raise ArticleConflictError(f"Article already exists: {values.slug}")
        post, experience_html, sources = self._normalize_input(values)
        row = ArticleTable(
            owner_reader_id=self._owner_reader_id,
            slug=post.slug,
            status=ArticleWorkflowStatus.DRAFT.value,
            **self._content_values(post, experience_html, sources, revision_notes),
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_detail(row)

    async def update_draft(
        self,
        values: PostInput | InteractivePostInput,
        revision_notes: str | None = None,
    ) -> ArticleDetail:
        """Replace the working copy while preserving one safe published snapshot."""
        article = await self._article_by_slug(values.slug, lock=True)
        if article is None:
            raise ArticleNotFoundError(f"Article not found: {values.slug}")
        if article.status not in {
            ArticleWorkflowStatus.DRAFT.value,
            ArticleWorkflowStatus.CHANGES_REQUESTED.value,
            ArticleWorkflowStatus.PUBLISHED.value,
        }:
            raise ArticleConflictError(
                "Articles under review or already approved cannot be edited."
            )
        post, experience_html, sources = self._normalize_input(values)
        content_hash = self._content_hash(post, experience_html, sources)
        if content_hash == article.content_hash:
            raise ArticleConflictError("The working article already has this content.")
        if article.status == ArticleWorkflowStatus.PUBLISHED.value:
            await self._capture_snapshot(article)
            article.review_cycle_id = None
        self._apply_content(
            article,
            post,
            experience_html,
            sources,
            revision_notes,
            content_hash,
        )
        article.status = ArticleWorkflowStatus.DRAFT.value
        article.submitted_content_hash = None
        article.reviewed_at = None
        article.updated_at = datetime.now(UTC)
        await self._session.flush()
        return self._to_detail(article)

    async def get_article(self, article_id: UUID) -> ArticleDetail:
        """Return the complete working copy by stable identifier."""
        article = await self._article_by_id(article_id)
        return self._to_detail(article)

    async def get_article_by_slug(self, slug: str) -> ArticleDetail:
        """Return the complete working copy by slug for MCP authoring."""
        article = await self._article_by_slug(slug)
        if article is None:
            raise ArticleNotFoundError(f"Article not found: {slug}")
        return self._to_detail(article)

    async def get_snapshot(self, article_id: UUID) -> ArticleSnapshot | None:
        """Return the last-published snapshot when one exists."""
        await self._article_by_id(article_id)
        row = await self._session.get(ArticleSnapshotTable, article_id)
        return self._to_snapshot(row) if row is not None else None

    async def submit_for_review(
        self, slug: str, expected_content_hash: str
    ) -> ArticleRecord:
        """Freeze the current content hash and enter human review."""
        article = await self._article_by_slug(slug, lock=True)
        if article is None:
            raise ArticleNotFoundError(f"Article not found: {slug}")
        if article.status != ArticleWorkflowStatus.DRAFT.value:
            raise ArticleConflictError("Only a draft can enter human review.")
        if article.content_hash != expected_content_hash:
            raise ArticleConflictError(
                "The article changed after it was fetched; submit its current "
                "content hash."
            )
        article.review_cycle_id = article.review_cycle_id or uuid4()
        article.submitted_content_hash = article.content_hash
        article.status = ArticleWorkflowStatus.IN_REVIEW.value
        article.updated_at = datetime.now(UTC)
        await self._session.flush()
        return self._to_record(article)

    async def publish(self, article_id: UUID) -> ArticleRecord:
        """Publish the approved working copy while retaining the prior snapshot."""
        article = await self._article_by_id(article_id, lock=True)
        if article.status != ArticleWorkflowStatus.APPROVED.value:
            raise ArticleConflictError("Only an approved article can be published.")
        if article.submitted_content_hash != article.content_hash:
            raise ArticleConflictError(
                "Approved content no longer matches the reviewed copy."
            )
        now = datetime.now(UTC)
        article.status = ArticleWorkflowStatus.PUBLISHED.value
        article.published_at = now
        article.updated_at = now
        await self._session.flush()
        return self._to_record(article)

    async def discard_draft(self, article_id: UUID) -> ArticleRecord:
        """Restore the safe snapshot and abandon an untrusted working draft."""
        article = await self._article_by_id(article_id, lock=True)
        if article.status == ArticleWorkflowStatus.PUBLISHED.value:
            raise ArticleConflictError(
                "Published articles do not have a draft to discard."
            )
        snapshot = await self._session.get(ArticleSnapshotTable, article_id)
        if snapshot is None:
            raise ArticleConflictError(
                "A new unpublished article has no snapshot to restore."
            )
        self._restore_snapshot(article, snapshot)
        await self._session.flush()
        return self._to_record(article)

    async def rollback(self, article_id: UUID) -> ArticleRecord:
        """Swap the current published article with its one-step backup."""
        article = await self._article_by_id(article_id, lock=True)
        if article.status != ArticleWorkflowStatus.PUBLISHED.value:
            raise ArticleConflictError("Only a published article can be rolled back.")
        snapshot = await self._session.get(ArticleSnapshotTable, article_id)
        if snapshot is None:
            raise ArticleConflictError(
                "This article has no previous publication snapshot."
            )
        current_values = self._snapshot_values(article)
        self._restore_snapshot(article, snapshot)
        for key, value in current_values.items():
            setattr(snapshot, key, value)
        snapshot.captured_at = datetime.now(UTC)
        await self._session.flush()
        return self._to_record(article)

    async def _public_content(self, slug: str) -> ArticleTable | ArticleSnapshotTable:
        result = await self._session.execute(
            select(ArticleTable, ArticleSnapshotTable)
            .outerjoin(
                ArticleSnapshotTable,
                ArticleSnapshotTable.article_id == ArticleTable.article_id,
            )
            .where(
                ArticleTable.owner_reader_id == self._owner_reader_id,
                ArticleTable.slug == slug,
            )
        )
        record = result.one_or_none()
        if record is None:
            raise ArticleNotFoundError(f"Published article not found: {slug}")
        article, snapshot = record
        if article.status != ArticleWorkflowStatus.PUBLISHED.value and snapshot is None:
            raise ArticleNotFoundError(f"Published article not found: {slug}")
        return self._public_row(article, snapshot)

    @staticmethod
    def _public_row(
        article: ArticleTable, snapshot: ArticleSnapshotTable | None
    ) -> ArticleTable | ArticleSnapshotTable:
        if article.status == ArticleWorkflowStatus.PUBLISHED.value:
            return article
        if snapshot is None:
            raise ArticleNotFoundError(f"Published article not found: {article.slug}")
        return snapshot

    async def _capture_snapshot(self, article: ArticleTable) -> None:
        snapshot = await self._session.get(ArticleSnapshotTable, article.article_id)
        values = self._snapshot_values(article)
        if snapshot is None:
            snapshot = ArticleSnapshotTable(article_id=article.article_id, **values)
            self._session.add(snapshot)
        else:
            for key, value in values.items():
                setattr(snapshot, key, value)
            snapshot.captured_at = datetime.now(UTC)

    @staticmethod
    def _snapshot_values(article: ArticleTable) -> dict[str, object]:
        if article.published_at is None:
            raise ArticleConflictError(
                "Published article is missing its publication time."
            )
        return {
            "slug": article.slug,
            "title": article.title,
            "publication_date": article.publication_date,
            "description": article.description,
            "tags": article.tags,
            "cover": article.cover,
            "featured": article.featured,
            "reading_html": article.reading_html,
            "experience_html": article.experience_html,
            "research_sources": article.research_sources,
            "content_hash": article.content_hash,
            "published_at": article.published_at,
        }

    @staticmethod
    def _restore_snapshot(
        article: ArticleTable, snapshot: ArticleSnapshotTable
    ) -> None:
        for field in (
            "title",
            "publication_date",
            "description",
            "tags",
            "cover",
            "featured",
            "reading_html",
            "experience_html",
            "research_sources",
            "content_hash",
            "published_at",
        ):
            setattr(article, field, getattr(snapshot, field))
        article.status = ArticleWorkflowStatus.PUBLISHED.value
        article.revision_notes = None
        article.review_cycle_id = None
        article.submitted_content_hash = None
        article.reviewed_at = None
        article.updated_at = datetime.now(UTC)

    @staticmethod
    def _normalize_input(
        values: PostInput | InteractivePostInput,
    ) -> tuple[PostInput, str | None, list[ResearchSource]]:
        if isinstance(values, InteractivePostInput):
            post = values.to_post_input()
            experience_html = values.experience_html
            sources = values.research_sources
        else:
            if values.experience is not None:
                raise ArticleConflictError(
                    "Use the interactive draft tool when an experience is present."
                )
            post = values
            experience_html = None
            sources = []
        cleaned_html = sanitize_article_html(post.html)
        if not cleaned_html:
            raise ArticleConflictError(
                "Reading HTML is empty after content-policy sanitization."
            )
        return post.model_copy(update={"html": cleaned_html}), experience_html, sources

    @classmethod
    def _content_values(
        cls,
        post: PostInput,
        experience_html: str | None,
        sources: list[ResearchSource],
        revision_notes: str | None,
    ) -> dict[str, object]:
        return {
            "title": post.title,
            "publication_date": post.date,
            "description": post.description,
            "tags": post.tags,
            "cover": post.cover,
            "featured": post.featured,
            "reading_html": post.html,
            "experience_html": experience_html,
            "research_sources": [
                source.model_dump(mode="json", by_alias=True) for source in sources
            ],
            "revision_notes": revision_notes,
            "content_hash": cls._content_hash(post, experience_html, sources),
        }

    @staticmethod
    def _apply_content(
        article: ArticleTable,
        post: PostInput,
        experience_html: str | None,
        sources: list[ResearchSource],
        revision_notes: str | None,
        content_hash: str,
    ) -> None:
        article.title = post.title
        article.publication_date = post.date
        article.description = post.description
        article.tags = post.tags
        article.cover = post.cover
        article.featured = post.featured
        article.reading_html = post.html
        article.experience_html = experience_html
        article.research_sources = [
            source.model_dump(mode="json", by_alias=True) for source in sources
        ]
        article.revision_notes = revision_notes
        article.content_hash = content_hash

    @staticmethod
    def _content_hash(
        post: PostInput,
        experience_html: str | None,
        sources: list[ResearchSource],
    ) -> str:
        payload = {
            "post": post.model_dump(mode="json", by_alias=True),
            "experienceHtml": experience_html,
            "researchSources": [
                source.model_dump(mode="json", by_alias=True) for source in sources
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()

    async def _article_by_slug(
        self, slug: str, *, lock: bool = False
    ) -> ArticleTable | None:
        statement = select(ArticleTable).where(
            ArticleTable.owner_reader_id == self._owner_reader_id,
            ArticleTable.slug == slug,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(ArticleTable | None, await self._session.scalar(statement))

    async def _article_by_id(
        self, article_id: UUID, *, lock: bool = False
    ) -> ArticleTable:
        statement = select(ArticleTable).where(
            ArticleTable.owner_reader_id == self._owner_reader_id,
            ArticleTable.article_id == article_id,
        )
        if lock:
            statement = statement.with_for_update()
        article = await self._session.scalar(statement)
        if article is None:
            raise ArticleNotFoundError(f"Article not found: {article_id}")
        return article

    @staticmethod
    def _reading_time(html: str) -> int:
        word_count = len(re.sub(r"<[^>]+>", " ", html).split())
        return max(1, (word_count + 209) // 210)

    @classmethod
    def _to_post(cls, row: ArticleTable | ArticleSnapshotTable) -> Post:
        return Post(
            title=row.title,
            slug=row.slug,
            date=row.publication_date,
            description=row.description,
            tags=row.tags,
            cover=row.cover,
            experience=(
                f"/posts/{row.slug}/experience"
                if row.experience_html is not None
                else None
            ),
            featured=row.featured,
            html=row.reading_html,
            reading_time=cls._reading_time(row.reading_html),
        )

    @classmethod
    def _summary_for(cls, row: ArticleTable | ArticleSnapshotTable) -> PostSummary:
        return PostSummary(**cls._to_post(row).model_dump(exclude={"html"}))

    @staticmethod
    def _to_record(row: ArticleTable) -> ArticleRecord:
        return ArticleRecord(
            article_id=row.article_id,
            slug=row.slug,
            status=row.status,
            review_cycle_id=row.review_cycle_id,
            submitted_content_hash=row.submitted_content_hash,
            created_at=row.created_at,
            updated_at=row.updated_at,
            published_at=row.published_at,
        )

    @classmethod
    def _to_detail(cls, row: ArticleTable) -> ArticleDetail:
        return ArticleDetail(
            **cls._to_record(row).model_dump(),
            post=cls._to_post(row),
            experience_html=row.experience_html,
            content_hash=row.content_hash,
            research_sources=[
                ResearchSource(**source) for source in row.research_sources
            ],
            revision_notes=row.revision_notes,
        )

    @classmethod
    def _to_snapshot(cls, row: ArticleSnapshotTable) -> ArticleSnapshot:
        return ArticleSnapshot(
            article_id=row.article_id,
            slug=row.slug,
            post=cls._to_post(row),
            experience_html=row.experience_html,
            content_hash=row.content_hash,
            research_sources=[
                ResearchSource(**source) for source in row.research_sources
            ],
            captured_at=row.captured_at,
            published_at=row.published_at,
        )
