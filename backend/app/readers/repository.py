"""Database persistence operations for reader profiles and reading state."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ReaderGroup,
    ReaderGroupInput,
    ReaderPreferences,
    ReaderPreferencesInput,
    ReadingState,
    ReadingStateInput,
)
from ..tables import ReaderGroupTable, ReaderProfileTable, ReadingStateTable


class ReaderRepository:
    """Stores and retrieves user-specific reader state in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a transactional session."""
        self._session = session

    async def get_preferences(self, reader_id: UUID) -> ReaderPreferences:
        """Return preferences, creating the anonymous reader when necessary."""
        profile = await self._get_or_create_profile(reader_id)
        return self._to_preferences(profile)

    async def update_preferences(
        self, reader_id: UUID, values: ReaderPreferencesInput
    ) -> ReaderPreferences:
        """Upsert display preferences for a reader."""
        profile = await self._get_or_create_profile(reader_id)
        profile.theme = values.theme
        profile.font_scale = values.font_scale
        profile.font_family = values.font_family
        profile.line_height = values.line_height
        profile.content_width = values.content_width
        await self._session.flush()
        await self._session.refresh(profile)
        return self._to_preferences(profile)

    async def list_reading_states(self, reader_id: UUID) -> list[ReadingState]:
        """List all reading states belonging to a reader."""
        await self._get_or_create_profile(reader_id)
        result = await self._session.scalars(
            select(ReadingStateTable).where(ReadingStateTable.reader_id == reader_id)
        )
        return [self._to_reading_state(row) for row in result]

    async def list_groups(self, reader_id: UUID) -> list[ReaderGroup]:
        """List a reader's custom groups in creation order."""
        await self._get_or_create_profile(reader_id)
        result = await self._session.scalars(
            select(ReaderGroupTable)
            .where(ReaderGroupTable.reader_id == reader_id)
            .order_by(ReaderGroupTable.created_at)
        )
        return [self._to_group(row) for row in result]

    async def create_group(
        self, reader_id: UUID, values: ReaderGroupInput
    ) -> ReaderGroup:
        """Create a named group belonging to one reader."""
        await self._get_or_create_profile(reader_id)
        group = ReaderGroupTable(
            reader_id=reader_id, name=values.name, color=values.color
        )
        self._session.add(group)
        await self._session.flush()
        await self._session.refresh(group)
        return self._to_group(group)

    async def update_group(
        self, reader_id: UUID, group_id: UUID, values: ReaderGroupInput
    ) -> ReaderGroup | None:
        """Rename or recolor a group owned by a reader."""
        group = await self._session.get(ReaderGroupTable, group_id)
        if group is None or group.reader_id != reader_id:
            return None
        group.name = values.name
        group.color = values.color
        await self._session.flush()
        await self._session.refresh(group)
        return self._to_group(group)

    async def delete_group(self, reader_id: UUID, group_id: UUID) -> bool:
        """Delete a reader-owned group without deleting its posts."""
        group = await self._session.get(ReaderGroupTable, group_id)
        if group is None or group.reader_id != reader_id:
            return False
        await self._session.delete(group)
        await self._session.flush()
        return True

    async def update_reading_state(
        self, reader_id: UUID, post_slug: str, values: ReadingStateInput
    ) -> ReadingState:
        """Upsert reading progress and collection flags for one post."""
        await self._get_or_create_profile(reader_id)
        if values.group_id is not None:
            group = await self._session.get(ReaderGroupTable, values.group_id)
            if group is None or group.reader_id != reader_id:
                raise ValueError("Group does not belong to this reader.")
        state = await self._session.get(ReadingStateTable, (reader_id, post_slug))
        if state is None:
            state = ReadingStateTable(reader_id=reader_id, post_slug=post_slug)
            self._session.add(state)
        state.is_favorite = values.is_favorite
        state.is_bookmarked = values.is_bookmarked
        state.progress_percent = values.progress_percent
        state.group_id = values.group_id
        if values.progress_percent > 0:
            state.last_read_at = func.now()
        await self._session.flush()
        await self._session.refresh(state)
        return self._to_reading_state(state)

    async def _get_or_create_profile(self, reader_id: UUID) -> ReaderProfileTable:
        profile = await self._session.get(ReaderProfileTable, reader_id)
        if profile is None:
            profile = ReaderProfileTable(reader_id=reader_id)
            self._session.add(profile)
            await self._session.flush()
            await self._session.refresh(profile)
        return profile

    @staticmethod
    def _to_preferences(row: ReaderProfileTable) -> ReaderPreferences:
        return ReaderPreferences(
            reader_id=row.reader_id,
            theme=row.theme,
            font_scale=row.font_scale,
            font_family=row.font_family,
            line_height=row.line_height,
            content_width=row.content_width,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_reading_state(row: ReadingStateTable) -> ReadingState:
        return ReadingState(
            reader_id=row.reader_id,
            post_slug=row.post_slug,
            is_favorite=row.is_favorite,
            is_bookmarked=row.is_bookmarked,
            progress_percent=row.progress_percent,
            group_id=row.group_id,
            updated_at=row.updated_at,
            last_read_at=row.last_read_at,
        )

    @staticmethod
    def _to_group(row: ReaderGroupTable) -> ReaderGroup:
        return ReaderGroup(
            group_id=row.group_id,
            reader_id=row.reader_id,
            name=row.name,
            color=row.color,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
