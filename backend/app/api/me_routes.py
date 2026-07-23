"""Authenticated reader endpoints whose ownership comes only from the JWT."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import IntegrityError

from ..articles.repository import ArticleNotFoundError, ArticleRepository
from ..auth.dependencies import Principal
from ..auth.mcp_credentials import McpCredentialRepository
from ..auth.models import (
    McpCredential,
    McpCredentialCreated,
    McpCredentialCreateInput,
)
from ..database import DatabaseSession
from ..learning_paths.repository import LearningPathRepository
from ..models import (
    LearningPath,
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

router = APIRouter(prefix="/api/v1/me", tags=["authenticated-reader"])


@router.get("/posts", response_model=list[PostSummary])
async def list_posts(
    principal: Principal, session: DatabaseSession
) -> list[PostSummary]:
    """List published articles belonging only to the current vault."""
    return await ArticleRepository(session, principal.reader_id).list_published()


@router.get("/posts/{slug}", response_model=Post)
async def get_post(slug: str, principal: Principal, session: DatabaseSession) -> Post:
    """Return one published article only when the current user owns it."""
    try:
        return await ArticleRepository(session, principal.reader_id).get_published(slug)
    except ArticleNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get(
    "/posts/{slug}/experience",
    response_class=PlainTextResponse,
)
async def get_post_experience(
    slug: str, principal: Principal, session: DatabaseSession
) -> PlainTextResponse:
    """Return an owned interactive document as inert sandbox input."""
    try:
        source = await ArticleRepository(
            session, principal.reader_id
        ).get_published_experience(slug)
    except ArticleNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return PlainTextResponse(source, media_type="text/plain; charset=utf-8")


@router.get("/preferences", response_model=ReaderPreferences)
async def get_preferences(
    principal: Principal, session: DatabaseSession
) -> ReaderPreferences:
    """Return the current account's display preferences."""
    return await ReaderRepository(session).get_preferences(principal.reader_id)


@router.put("/preferences", response_model=ReaderPreferences)
async def update_preferences(
    values: ReaderPreferencesInput,
    principal: Principal,
    session: DatabaseSession,
) -> ReaderPreferences:
    """Update only the current account's display preferences."""
    return await ReaderRepository(session).update_preferences(
        principal.reader_id, values
    )


@router.get("/reading-states", response_model=list[ReadingState])
async def list_reading_states(
    principal: Principal, session: DatabaseSession
) -> list[ReadingState]:
    """List only the current account's reading state."""
    return await ReaderRepository(session).list_reading_states(principal.reader_id)


@router.put("/reading-states/{post_slug}", response_model=ReadingState)
async def update_reading_state(
    post_slug: str,
    values: ReadingStateInput,
    principal: Principal,
    session: DatabaseSession,
) -> ReadingState:
    """Update one article state owned by the current account."""
    if not post_slug or len(post_slug) > 160:
        raise HTTPException(status_code=422, detail="Invalid post slug.")
    try:
        await ArticleRepository(session, principal.reader_id).get_published(post_slug)
        return await ReaderRepository(session).update_reading_state(
            principal.reader_id, post_slug, values
        )
    except ArticleNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/groups", response_model=list[ReaderGroup])
async def list_groups(
    principal: Principal, session: DatabaseSession
) -> list[ReaderGroup]:
    """List only the current account's collections."""
    return await ReaderRepository(session).list_groups(principal.reader_id)


@router.post("/groups", response_model=ReaderGroup, status_code=status.HTTP_201_CREATED)
async def create_group(
    values: ReaderGroupInput,
    principal: Principal,
    session: DatabaseSession,
) -> ReaderGroup:
    """Create a collection owned by the current account."""
    try:
        return await ReaderRepository(session).create_group(principal.reader_id, values)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409, detail="A group with this name already exists."
        ) from error


@router.put("/groups/{group_id}", response_model=ReaderGroup)
async def update_group(
    group_id: UUID,
    values: ReaderGroupInput,
    principal: Principal,
    session: DatabaseSession,
) -> ReaderGroup:
    """Update a collection only when the current account owns it."""
    group = await ReaderRepository(session).update_group(
        principal.reader_id, group_id, values
    )
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    return group


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: UUID, principal: Principal, session: DatabaseSession
) -> Response:
    """Delete a collection only when the current account owns it."""
    if not await ReaderRepository(session).delete_group(principal.reader_id, group_id):
        raise HTTPException(status_code=404, detail="Group not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/learning-paths", response_model=list[LearningPath])
async def list_learning_paths(
    principal: Principal, session: DatabaseSession
) -> list[LearningPath]:
    """Project account-owned progress onto published curricula."""
    return await LearningPathRepository(session, principal.reader_id).list_paths(
        principal.reader_id
    )


@router.get("/learning-paths/{path_slug}", response_model=LearningPath)
async def get_learning_path(
    path_slug: str, principal: Principal, session: DatabaseSession
) -> LearningPath:
    """Return one curriculum with account-owned lesson state."""
    return await LearningPathRepository(session, principal.reader_id).get_path(
        path_slug, principal.reader_id
    )


@router.get("/mcp-credentials", response_model=list[McpCredential])
async def list_mcp_credentials(
    principal: Principal, session: DatabaseSession
) -> list[McpCredential]:
    """List revocable MCP credentials for the current private vault."""
    return await McpCredentialRepository(session).list(principal)


@router.post(
    "/mcp-credentials",
    response_model=McpCredentialCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp_credential(
    values: McpCredentialCreateInput,
    principal: Principal,
    session: DatabaseSession,
) -> McpCredentialCreated:
    """Create a personal MCP token whose plaintext is returned once."""
    return await McpCredentialRepository(session).create(principal, values)


@router.delete(
    "/mcp-credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_mcp_credential(
    credential_id: UUID,
    principal: Principal,
    session: DatabaseSession,
) -> Response:
    """Revoke one MCP credential owned by the current vault."""
    if not await McpCredentialRepository(session).revoke(principal, credential_id):
        raise HTTPException(status_code=404, detail="MCP credential not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
