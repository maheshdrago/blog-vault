"""Protected REST endpoints for the human article review dashboard."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..articles.repository import (
    ArticleConflictError,
    ArticleNotFoundError,
    ArticleRepository,
)
from ..database import DatabaseSession
from ..models import (
    ArticleRecord,
    ArticleReviewComment,
    ArticleReviewCommentInput,
    ArticleReviewContext,
    ArticleReviewQueueItem,
    ArticleReviewResolutionInput,
)
from ..review.repository import ReviewRepository
from ..security import require_admin_token

router = APIRouter(
    prefix="/api/v1/admin/reviews",
    dependencies=[Depends(require_admin_token)],
    tags=["article-review"],
)


def _http_error(error: Exception) -> HTTPException:
    """Translate known review-domain failures to stable HTTP responses."""
    status_code = 404 if isinstance(error, ArticleNotFoundError) else 409
    return HTTPException(status_code=status_code, detail=str(error))


@router.get("", response_model=list[ArticleReviewQueueItem])
async def list_review_queue(
    session: DatabaseSession,
    include_published: bool = Query(default=False, alias="includePublished"),
) -> list[ArticleReviewQueueItem]:
    """List articles awaiting review, revision, or publication."""
    return await ReviewRepository(session).list_queue(
        include_published=include_published
    )


@router.get("/{article_id}", response_model=ArticleReviewContext)
async def get_review_context(
    article_id: UUID, session: DatabaseSession
) -> ArticleReviewContext:
    """Return the working article, public snapshot, and persisted feedback."""
    try:
        return await ReviewRepository(session).get_context(article_id)
    except (ArticleNotFoundError, ArticleConflictError) as error:
        raise _http_error(error) from error


@router.post(
    "/{article_id}/comments",
    response_model=ArticleReviewComment,
    status_code=status.HTTP_201_CREATED,
)
async def create_review_comment(
    article_id: UUID,
    values: ArticleReviewCommentInput,
    session: DatabaseSession,
) -> ArticleReviewComment:
    """Attach human feedback to the active article review cycle."""
    try:
        return await ReviewRepository(session).add_human_comment(article_id, values)
    except (ArticleNotFoundError, ArticleConflictError) as error:
        raise _http_error(error) from error


@router.put(
    "/comments/{comment_id}/resolution",
    response_model=ArticleReviewComment,
)
async def resolve_review_comment(
    comment_id: UUID,
    values: ArticleReviewResolutionInput,
    session: DatabaseSession,
) -> ArticleReviewComment:
    """Resolve or reopen a root comment after human verification."""
    try:
        return await ReviewRepository(session).set_comment_resolved(
            comment_id, resolved=values.resolved
        )
    except (ArticleNotFoundError, ArticleConflictError) as error:
        raise _http_error(error) from error


@router.post("/{article_id}/request-changes", response_model=ArticleReviewContext)
async def request_article_changes(
    article_id: UUID, session: DatabaseSession
) -> ArticleReviewContext:
    """Return the working article to an assistant with unresolved feedback."""
    try:
        return await ReviewRepository(session).request_changes(article_id)
    except (ArticleNotFoundError, ArticleConflictError) as error:
        raise _http_error(error) from error


@router.post("/{article_id}/approve", response_model=ArticleReviewContext)
async def approve_article(
    article_id: UUID, session: DatabaseSession
) -> ArticleReviewContext:
    """Approve an article only after every feedback thread is resolved."""
    try:
        return await ReviewRepository(session).approve(article_id)
    except (ArticleNotFoundError, ArticleConflictError) as error:
        raise _http_error(error) from error


@router.post("/{article_id}/publish", response_model=ArticleRecord)
async def publish_article(article_id: UUID, session: DatabaseSession) -> ArticleRecord:
    """Publish an approved article without exposing this action to MCP."""
    try:
        return await ArticleRepository(session).publish(article_id)
    except (ArticleNotFoundError, ArticleConflictError) as error:
        raise _http_error(error) from error


@router.post("/{article_id}/discard-draft", response_model=ArticleRecord)
async def discard_article_draft(
    article_id: UUID, session: DatabaseSession
) -> ArticleRecord:
    """Restore the last published snapshot over an untrusted working draft."""
    try:
        return await ArticleRepository(session).discard_draft(article_id)
    except (ArticleNotFoundError, ArticleConflictError) as error:
        raise _http_error(error) from error


@router.post("/{article_id}/rollback", response_model=ArticleRecord)
async def rollback_article(article_id: UUID, session: DatabaseSession) -> ArticleRecord:
    """Swap a published article with its one-step human-controlled backup."""
    try:
        return await ArticleRepository(session).rollback(article_id)
    except (ArticleNotFoundError, ArticleConflictError) as error:
        raise _http_error(error) from error
