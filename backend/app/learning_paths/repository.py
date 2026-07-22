"""Persistence for curated article categories and ordered learning paths."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..articles.repository import ArticleNotFoundError, ArticleRepository
from ..models import (
    LearningPath,
    LearningPathInput,
    LearningPathLesson,
    LearningPathLessonInput,
    LearningPathSection,
    LearningPathSectionInput,
    PostSummary,
)
from ..tables import (
    ArticleTable,
    LearningPathLessonTable,
    LearningPathSectionTable,
    LearningPathTable,
    ReadingStateTable,
)


class LearningPathRepository:
    """Own curriculum structure and project reader progress onto its lessons."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_paths(self, reader_id: UUID | None = None) -> list[LearningPath]:
        """Return published paths with ordered categories, lessons, and progress."""
        paths = await self._session.scalars(
            select(LearningPathTable)
            .where(LearningPathTable.is_published.is_(True))
            .order_by(LearningPathTable.sort_order, LearningPathTable.title)
        )
        return [await self._to_path(path, reader_id) for path in paths]

    async def get_path(self, slug: str, reader_id: UUID | None = None) -> LearningPath:
        """Return one complete path by stable slug."""
        path = await self._session.scalar(
            select(LearningPathTable).where(LearningPathTable.slug == slug)
        )
        if path is None:
            raise ArticleNotFoundError(f"Learning path not found: {slug}")
        return await self._to_path(path, reader_id)

    async def create_path(self, values: LearningPathInput) -> LearningPath:
        """Append a new published curriculum."""
        latest = await self._session.scalar(
            select(func.max(LearningPathTable.sort_order))
        )
        row = LearningPathTable(
            slug=values.slug,
            title=values.title,
            description=values.description,
            icon=values.icon,
            sort_order=(latest or 0) + 1,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return await self._to_path(row, None)

    async def add_section(
        self, path_slug: str, values: LearningPathSectionInput
    ) -> LearningPath:
        """Append a category to an existing path."""
        path = await self._path_row(path_slug)
        latest = await self._session.scalar(
            select(func.max(LearningPathSectionTable.sort_order)).where(
                LearningPathSectionTable.path_id == path.path_id
            )
        )
        self._session.add(
            LearningPathSectionTable(
                path_id=path.path_id,
                title=values.title,
                icon=values.icon,
                sort_order=(latest or 0) + 1,
            )
        )
        await self._session.flush()
        return await self._to_path(path, None)

    async def add_lesson(
        self,
        path_slug: str,
        section_title: str,
        values: LearningPathLessonInput,
    ) -> LearningPath:
        """Append one published article to a category."""
        path = await self._path_row(path_slug)
        section = await self._session.scalar(
            select(LearningPathSectionTable).where(
                LearningPathSectionTable.path_id == path.path_id,
                LearningPathSectionTable.title == section_title,
            )
        )
        if section is None:
            raise ArticleNotFoundError(
                f"Learning path section not found: {section_title}"
            )
        article = await self._session.scalar(
            select(ArticleTable).where(ArticleTable.slug == values.article_slug)
        )
        if article is None:
            raise ArticleNotFoundError(f"Article not found: {values.article_slug}")
        latest = await self._session.scalar(
            select(func.max(LearningPathLessonTable.sort_order)).where(
                LearningPathLessonTable.section_id == section.section_id
            )
        )
        self._session.add(
            LearningPathLessonTable(
                path_id=path.path_id,
                section_id=section.section_id,
                article_id=article.article_id,
                sort_order=(latest or 0) + 1,
                is_required=values.is_required,
            )
        )
        await self._session.flush()
        return await self._to_path(path, None)

    async def _path_row(self, slug: str) -> LearningPathTable:
        path = await self._session.scalar(
            select(LearningPathTable).where(LearningPathTable.slug == slug)
        )
        if path is None:
            raise ArticleNotFoundError(f"Learning path not found: {slug}")
        return path

    async def _to_path(
        self, path: LearningPathTable, reader_id: UUID | None
    ) -> LearningPath:
        section_rows = await self._session.scalars(
            select(LearningPathSectionTable)
            .where(LearningPathSectionTable.path_id == path.path_id)
            .order_by(
                LearningPathSectionTable.sort_order,
                LearningPathSectionTable.title,
            )
        )
        sections: list[LearningPathSection] = []
        completed = 0
        progress_total = 0
        total = 0
        prerequisite_met = True
        articles = ArticleRepository(self._session)
        for section in section_rows:
            lesson_rows = await self._session.execute(
                select(LearningPathLessonTable, ArticleTable.slug)
                .join(
                    ArticleTable,
                    ArticleTable.article_id == LearningPathLessonTable.article_id,
                )
                .where(LearningPathLessonTable.section_id == section.section_id)
                .order_by(LearningPathLessonTable.sort_order)
            )
            lessons: list[LearningPathLesson] = []
            for lesson, article_slug in lesson_rows:
                try:
                    post = await articles.get_published(article_slug)
                except ArticleNotFoundError:
                    continue
                progress = 0
                if reader_id is not None:
                    state = await self._session.get(
                        ReadingStateTable, (reader_id, article_slug)
                    )
                    progress = state.progress_percent if state is not None else 0
                is_completed, is_locked, prerequisite_met = self._lesson_state(
                    progress, prerequisite_met, lesson.is_required
                )
                lessons.append(
                    LearningPathLesson(
                        lesson_id=lesson.lesson_id,
                        article=PostSummary(**post.model_dump(exclude={"html"})),
                        sort_order=lesson.sort_order,
                        is_required=lesson.is_required,
                        progress_percent=progress,
                        is_completed=is_completed,
                        is_locked=is_locked,
                    )
                )
                total += 1
                completed += int(is_completed)
                progress_total += progress
            sections.append(
                LearningPathSection(
                    section_id=section.section_id,
                    title=section.title,
                    icon=section.icon,
                    sort_order=section.sort_order,
                    lessons=lessons,
                )
            )
        return LearningPath(
            path_id=path.path_id,
            slug=path.slug,
            title=path.title,
            description=path.description,
            icon=path.icon,
            sort_order=path.sort_order,
            completed_lessons=completed,
            total_lessons=total,
            progress_percent=self._path_progress(progress_total, total),
            sections=sections,
        )

    @staticmethod
    def _path_progress(progress_total: int, lesson_count: int) -> int:
        """Average lesson reading progress into one path-level percentage."""
        return round(progress_total / lesson_count) if lesson_count else 0

    @staticmethod
    def _lesson_state(
        progress: int, prerequisite_met: bool, is_required: bool
    ) -> tuple[bool, bool, bool]:
        """Derive completion, locking, and the next prerequisite state."""
        is_completed = progress == 100
        is_locked = not prerequisite_met and not is_completed
        next_prerequisite = prerequisite_met and (is_completed or not is_required)
        return is_completed, is_locked, next_prerequisite
