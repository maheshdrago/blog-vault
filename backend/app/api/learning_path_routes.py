"""REST endpoints for curated learning paths and reader progress."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..articles.repository import ArticleNotFoundError
from ..database import DatabaseSession
from ..learning_paths.repository import LearningPathRepository
from ..models import LearningPath

router = APIRouter(prefix="/api/v1", tags=["learning-paths"])


@router.get("/learning-paths", response_model=list[LearningPath])
async def list_learning_paths(session: DatabaseSession) -> list[LearningPath]:
    """List published curricula without reader-specific completion state."""
    return await LearningPathRepository(session).list_paths()


@router.get("/readers/{reader_id}/learning-paths", response_model=list[LearningPath])
async def list_reader_learning_paths(
    reader_id: UUID, session: DatabaseSession
) -> list[LearningPath]:
    """Project one reader's article progress onto every published curriculum."""
    return await LearningPathRepository(session).list_paths(reader_id)


@router.get(
    "/readers/{reader_id}/learning-paths/{path_slug}", response_model=LearningPath
)
async def get_reader_learning_path(
    reader_id: UUID, path_slug: str, session: DatabaseSession
) -> LearningPath:
    """Return one reader-specific path for lesson navigation."""
    try:
        return await LearningPathRepository(session).get_path(path_slug, reader_id)
    except ArticleNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
