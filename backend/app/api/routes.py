"""REST endpoints for health, published articles, and persistent reader state."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import IntegrityError

from ..articles.repository import ArticleNotFoundError, ArticleRepository
from ..config import settings
from ..database import DatabaseSession
from ..models import (
    HealthResponse,
    Post,
    PostSummary,
    ReaderGroup,
    ReaderGroupInput,
    ReaderPreferences,
    ReaderPreferencesInput,
    ReadingState,
    ReadingStateInput,
)
from ..readers.repository import ReaderRepository

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return service readiness and external integration configuration."""
    return HealthResponse(
        status="ok",
        database_configured=settings.database_url is not None,
        article_review_configured=settings.admin_access_token is not None,
        telemetry_configured=settings.langfuse_configured,
    )


@router.get("/posts", response_model=list[PostSummary], tags=["articles"])
async def list_posts(session: DatabaseSession) -> list[PostSummary]:
    """Return metadata for all currently published articles."""
    return await ArticleRepository(session).list_published()


@router.get("/posts/{slug}", response_model=Post, tags=["articles"])
async def get_post(slug: str, session: DatabaseSession) -> Post:
    """Return the safe published copy of one article."""
    try:
        return await ArticleRepository(session).get_published(slug)
    except ArticleNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get(
    "/posts/{slug}/experience",
    response_class=PlainTextResponse,
    tags=["articles"],
)
async def get_post_experience(slug: str, session: DatabaseSession) -> PlainTextResponse:
    """Return an interactive document as inert text for sandboxed rendering."""
    try:
        source = await ArticleRepository(session).get_published_experience(slug)
    except ArticleNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return PlainTextResponse(source, media_type="text/plain; charset=utf-8")


@router.get(
    "/readers/{reader_id}/preferences",
    response_model=ReaderPreferences,
    tags=["reader-state"],
)
async def get_reader_preferences(
    reader_id: UUID, session: DatabaseSession
) -> ReaderPreferences:
    """Return preferences for an anonymous reader identifier."""
    return await ReaderRepository(session).get_preferences(reader_id)


@router.put(
    "/readers/{reader_id}/preferences",
    response_model=ReaderPreferences,
    tags=["reader-state"],
)
async def update_reader_preferences(
    reader_id: UUID,
    values: ReaderPreferencesInput,
    session: DatabaseSession,
) -> ReaderPreferences:
    """Update preferences for an anonymous reader identifier."""
    return await ReaderRepository(session).update_preferences(reader_id, values)


@router.get(
    "/readers/{reader_id}/reading-states",
    response_model=list[ReadingState],
    tags=["reader-state"],
)
async def list_reading_states(
    reader_id: UUID, session: DatabaseSession
) -> list[ReadingState]:
    """List bookmarks, favorites, and progress for a reader."""
    return await ReaderRepository(session).list_reading_states(reader_id)


@router.put(
    "/readers/{reader_id}/reading-states/{post_slug}",
    response_model=ReadingState,
    tags=["reader-state"],
)
async def update_reading_state(
    reader_id: UUID,
    post_slug: str,
    values: ReadingStateInput,
    session: DatabaseSession,
) -> ReadingState:
    """Upsert bookmark, favorite, and reading progress for one post."""
    if not post_slug or len(post_slug) > 160:
        raise HTTPException(status_code=422, detail="Invalid post slug.")
    try:
        return await ReaderRepository(session).update_reading_state(
            reader_id, post_slug, values
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get(
    "/readers/{reader_id}/groups",
    response_model=list[ReaderGroup],
    tags=["reader-state"],
)
async def list_reader_groups(
    reader_id: UUID, session: DatabaseSession
) -> list[ReaderGroup]:
    """List personal groups belonging to a reader."""
    return await ReaderRepository(session).list_groups(reader_id)


@router.post(
    "/readers/{reader_id}/groups",
    response_model=ReaderGroup,
    status_code=status.HTTP_201_CREATED,
    tags=["reader-state"],
)
async def create_reader_group(
    reader_id: UUID,
    values: ReaderGroupInput,
    session: DatabaseSession,
) -> ReaderGroup:
    """Create a personal blog group for a reader."""
    try:
        return await ReaderRepository(session).create_group(reader_id, values)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409, detail="A group with this name already exists."
        ) from error


@router.put(
    "/readers/{reader_id}/groups/{group_id}",
    response_model=ReaderGroup,
    tags=["reader-state"],
)
async def update_reader_group(
    reader_id: UUID,
    group_id: UUID,
    values: ReaderGroupInput,
    session: DatabaseSession,
) -> ReaderGroup:
    """Rename or recolor a personal group."""
    group = await ReaderRepository(session).update_group(reader_id, group_id, values)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    return group


@router.delete(
    "/readers/{reader_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["reader-state"],
)
async def delete_reader_group(
    reader_id: UUID, group_id: UUID, session: DatabaseSession
) -> Response:
    """Delete a group and move its posts back to Ungrouped."""
    deleted = await ReaderRepository(session).delete_group(reader_id, group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Group not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
