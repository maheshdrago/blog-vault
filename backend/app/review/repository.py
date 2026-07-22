"""Persistence and state transitions for article-based human review."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..articles.repository import (
    ArticleConflictError,
    ArticleNotFoundError,
    ArticleRepository,
)
from ..models import (
    ArticleReviewComment,
    ArticleReviewCommentInput,
    ArticleReviewContext,
    ArticleReviewQueueItem,
    ArticleReviewReplyInput,
    ArticleWorkflowStatus,
    ReviewCommentAuthor,
    ReviewCommentStatus,
)
from ..tables import ArticleReviewCommentTable, ArticleSnapshotTable, ArticleTable

_REVIEW_QUEUE_STATUSES = (
    ArticleWorkflowStatus.DRAFT.value,
    ArticleWorkflowStatus.IN_REVIEW.value,
    ArticleWorkflowStatus.CHANGES_REQUESTED.value,
    ArticleWorkflowStatus.APPROVED.value,
)


class ReviewRepository:
    """Own feedback and review transitions for the current working article."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a transaction-scoped session."""
        self._session = session

    async def list_queue(
        self,
        *,
        status: ArticleWorkflowStatus | None = None,
        include_published: bool = False,
    ) -> list[ArticleReviewQueueItem]:
        """List articles requiring review, revision, or publication."""
        statuses = (status.value,) if status is not None else _REVIEW_QUEUE_STATUSES
        if include_published and status is None:
            statuses = (*statuses, ArticleWorkflowStatus.PUBLISHED.value)
        rows = await self._session.scalars(
            select(ArticleTable)
            .where(ArticleTable.status.in_(statuses))
            .order_by(ArticleTable.updated_at.desc())
        )
        result: list[ArticleReviewQueueItem] = []
        for article in rows:
            if (
                article.status == ArticleWorkflowStatus.DRAFT.value
                and article.review_cycle_id is None
            ):
                continue
            if (
                article.status == ArticleWorkflowStatus.PUBLISHED.value
                and await self._session.get(ArticleSnapshotTable, article.article_id)
                is None
            ):
                continue
            counts: dict[str, int] = {}
            if article.review_cycle_id is not None:
                count_rows = (
                    await self._session.execute(
                        select(
                            ArticleReviewCommentTable.status,
                            func.count(ArticleReviewCommentTable.comment_id),
                        )
                        .where(
                            ArticleReviewCommentTable.article_id == article.article_id,
                            ArticleReviewCommentTable.review_cycle_id
                            == article.review_cycle_id,
                            ArticleReviewCommentTable.parent_comment_id.is_(None),
                        )
                        .group_by(ArticleReviewCommentTable.status)
                    )
                ).all()
                counts = {comment_status: count for comment_status, count in count_rows}
            result.append(
                ArticleReviewQueueItem(
                    **ArticleRepository._to_record(article).model_dump(),
                    title=article.title,
                    description=article.description,
                    open_comments=counts.get(ReviewCommentStatus.OPEN.value, 0),
                    addressed_comments=counts.get(
                        ReviewCommentStatus.ADDRESSED.value, 0
                    ),
                )
            )
        return result

    async def get_context(self, article_id: UUID) -> ArticleReviewContext:
        """Return the working article, safe snapshot, and active feedback."""
        articles = ArticleRepository(self._session)
        article = await articles.get_article(article_id)
        comments = (
            await self.list_comments(article_id, article.review_cycle_id)
            if article.review_cycle_id is not None
            else []
        )
        return ArticleReviewContext(
            article=article,
            published_snapshot=await articles.get_snapshot(article_id),
            comments=comments,
        )

    async def list_comments(
        self, article_id: UUID, review_cycle_id: UUID
    ) -> list[ArticleReviewComment]:
        """List root comments and replies for one active review cycle."""
        rows = await self._session.scalars(
            select(ArticleReviewCommentTable)
            .where(
                ArticleReviewCommentTable.article_id == article_id,
                ArticleReviewCommentTable.review_cycle_id == review_cycle_id,
            )
            .order_by(ArticleReviewCommentTable.created_at)
        )
        return [self._to_comment(row) for row in rows]

    async def add_human_comment(
        self, article_id: UUID, values: ArticleReviewCommentInput
    ) -> ArticleReviewComment:
        """Attach feedback to the article's active review cycle."""
        article = await self._reviewable_article(article_id)
        if article.status == ArticleWorkflowStatus.APPROVED.value:
            raise ArticleConflictError("Approved articles cannot receive new comments.")
        if article.review_cycle_id is None:
            raise ArticleConflictError("The article has no active review cycle.")
        row = ArticleReviewCommentTable(
            article_id=article_id,
            review_cycle_id=article.review_cycle_id,
            author=ReviewCommentAuthor.HUMAN.value,
            body=values.body,
            anchor_type=values.anchor_type.value,
            anchor_value=values.anchor_value,
            status=ReviewCommentStatus.OPEN.value,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_comment(row)

    async def reply_as_assistant(
        self, comment_id: UUID, values: ArticleReviewReplyInput
    ) -> ArticleReviewComment:
        """Reply to human feedback and mark it ready for confirmation."""
        parent = await self._session.get(ArticleReviewCommentTable, comment_id)
        if parent is None or parent.parent_comment_id is not None:
            raise ArticleNotFoundError(f"Root review comment not found: {comment_id}")
        if parent.author != ReviewCommentAuthor.HUMAN.value:
            raise ArticleConflictError("Assistant replies require a human comment.")
        if parent.status == ReviewCommentStatus.RESOLVED.value:
            raise ArticleConflictError("Resolved comments cannot receive new replies.")
        article = await self._session.get(ArticleTable, parent.article_id)
        if article is None:
            raise ArticleNotFoundError(f"Article not found: {parent.article_id}")
        if article.review_cycle_id != parent.review_cycle_id:
            raise ArticleConflictError("This comment belongs to a closed review cycle.")
        if article.status not in {
            ArticleWorkflowStatus.DRAFT.value,
            ArticleWorkflowStatus.IN_REVIEW.value,
            ArticleWorkflowStatus.CHANGES_REQUESTED.value,
        }:
            raise ArticleConflictError("This article is no longer open for revision.")
        row = ArticleReviewCommentTable(
            article_id=parent.article_id,
            review_cycle_id=parent.review_cycle_id,
            parent_comment_id=parent.comment_id,
            author=ReviewCommentAuthor.ASSISTANT.value,
            body=values.body,
            anchor_type=parent.anchor_type,
            anchor_value=parent.anchor_value,
            status=ReviewCommentStatus.ADDRESSED.value,
        )
        parent.status = ReviewCommentStatus.ADDRESSED.value
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._to_comment(row)

    async def set_comment_resolved(
        self, comment_id: UUID, *, resolved: bool
    ) -> ArticleReviewComment:
        """Let the reviewer resolve or reopen a root comment."""
        row = await self._session.get(ArticleReviewCommentTable, comment_id)
        if row is None or row.parent_comment_id is not None:
            raise ArticleNotFoundError(f"Root review comment not found: {comment_id}")
        article = await self._session.get(ArticleTable, row.article_id)
        if article is None or article.review_cycle_id != row.review_cycle_id:
            raise ArticleConflictError("This comment belongs to a closed review cycle.")
        row.status = (
            ReviewCommentStatus.RESOLVED.value
            if resolved
            else ReviewCommentStatus.OPEN.value
        )
        row.resolved_at = datetime.now(UTC) if resolved else None
        await self._session.flush()
        return self._to_comment(row)

    async def request_changes(self, article_id: UUID) -> ArticleReviewContext:
        """Return an in-review article to the assistant with durable feedback."""
        article = await self._article_with_status(
            article_id, ArticleWorkflowStatus.IN_REVIEW
        )
        if article.review_cycle_id is None:
            raise ArticleConflictError("The article has no active review cycle.")
        actionable = await self._session.scalar(
            select(func.count(ArticleReviewCommentTable.comment_id)).where(
                ArticleReviewCommentTable.article_id == article_id,
                ArticleReviewCommentTable.review_cycle_id == article.review_cycle_id,
                ArticleReviewCommentTable.parent_comment_id.is_(None),
                ArticleReviewCommentTable.author == ReviewCommentAuthor.HUMAN.value,
                ArticleReviewCommentTable.status != ReviewCommentStatus.RESOLVED.value,
            )
        )
        if not actionable:
            raise ArticleConflictError(
                "Add at least one unresolved review comment before requesting changes."
            )
        article.status = ArticleWorkflowStatus.CHANGES_REQUESTED.value
        article.submitted_content_hash = None
        article.updated_at = datetime.now(UTC)
        await self._session.flush()
        return await self.get_context(article_id)

    async def approve(self, article_id: UUID) -> ArticleReviewContext:
        """Approve the submitted hash after every active thread is resolved."""
        article = await self._article_with_status(
            article_id, ArticleWorkflowStatus.IN_REVIEW
        )
        if article.review_cycle_id is None:
            raise ArticleConflictError("The article has no active review cycle.")
        if article.submitted_content_hash != article.content_hash:
            raise ArticleConflictError("The article changed after review submission.")
        unresolved = await self._session.scalar(
            select(func.count(ArticleReviewCommentTable.comment_id)).where(
                ArticleReviewCommentTable.article_id == article_id,
                ArticleReviewCommentTable.review_cycle_id == article.review_cycle_id,
                ArticleReviewCommentTable.parent_comment_id.is_(None),
                ArticleReviewCommentTable.status != ReviewCommentStatus.RESOLVED.value,
            )
        )
        if unresolved:
            raise ArticleConflictError(
                "Resolve every review comment before approving this article."
            )
        article.status = ArticleWorkflowStatus.APPROVED.value
        article.reviewed_at = datetime.now(UTC)
        article.updated_at = article.reviewed_at
        await self._session.flush()
        return await self.get_context(article_id)

    async def _reviewable_article(self, article_id: UUID) -> ArticleTable:
        article = await self._session.get(ArticleTable, article_id)
        if article is None:
            raise ArticleNotFoundError(f"Article not found: {article_id}")
        if article.status not in _REVIEW_QUEUE_STATUSES:
            raise ArticleConflictError("This article is not in the review workflow.")
        return article

    async def _article_with_status(
        self, article_id: UUID, expected: ArticleWorkflowStatus
    ) -> ArticleTable:
        article = await self._reviewable_article(article_id)
        if article.status != expected.value:
            raise ArticleConflictError(
                f"Article must be {expected.value} for this action."
            )
        return article

    @staticmethod
    def _to_comment(row: ArticleReviewCommentTable) -> ArticleReviewComment:
        return ArticleReviewComment(
            comment_id=row.comment_id,
            article_id=row.article_id,
            review_cycle_id=row.review_cycle_id,
            parent_comment_id=row.parent_comment_id,
            author=row.author,
            body=row.body,
            anchor_type=row.anchor_type,
            anchor_value=row.anchor_value,
            status=row.status,
            created_at=row.created_at,
            resolved_at=row.resolved_at,
        )
