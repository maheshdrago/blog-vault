"""Idempotently seed the initial curated Blog Vault learning paths."""

import asyncio
from typing import TypedDict

from backend.app.database import database_session
from backend.app.learning_paths.repository import LearningPathRepository
from backend.app.models import (
    LearningPathInput,
    LearningPathLessonInput,
    LearningPathSectionInput,
)


class SeedPath(TypedDict):
    """Typed definition for an idempotently seeded learning path."""

    path: LearningPathInput
    sections: tuple[tuple[str, str, tuple[str, ...]], ...]


PATHS: tuple[SeedPath, ...] = (
    {
        "path": LearningPathInput(
            slug="systems-ai-foundations",
            title="Systems & AI Foundations",
            description=(
                "Build a grounded mental model of protocols, infrastructure, data "
                "changes, and the systems underneath modern AI applications."
            ),
            icon="core",
        ),
        "sections": (
            ("Core Concepts", "book", ("the-power-of-systems",)),
            (
                "Infrastructure & Security",
                "patterns",
                (
                    "what-happens-when-an-llm-calls-an-mcp-tool",
                    "the-anatomy-of-staying-logged-in",
                    "where-encryption-gets-opened",
                ),
            ),
            (
                "Data Systems",
                "technology",
                (
                    "you-cant-canary-a-database",
                    "how-your-pdf-becomes-a-conversation",
                ),
            ),
            (
                "AI Engineering",
                "advanced",
                ("how-ai-coding-tools-remember",),
            ),
        ),
    },
    {
        "path": LearningPathInput(
            slug="creative-practice",
            title="Creative Practice",
            description=(
                "A deliberate sequence for reading, thinking clearly, building, "
                "and sustaining meaningful creative work."
            ),
            icon="compass",
        ),
        "sections": (
            (
                "Thinking",
                "book",
                ("how-i-read", "notes-on-creativity"),
            ),
            (
                "Craft",
                "patterns",
                ("designing-for-clarity", "the-art-of-building"),
            ),
            (
                "Sustainable Work",
                "advanced",
                ("slow-productivity", "lessons-from-mistakes"),
            ),
        ),
    },
)


async def seed() -> None:
    """Create missing paths, sections, and lessons without reordering existing work."""
    async with database_session() as session:
        repository = LearningPathRepository(session)
        existing_paths = {path.slug: path for path in await repository.list_paths()}
        for definition in PATHS:
            path_input = definition["path"]
            if path_input.slug not in existing_paths:
                await repository.create_path(path_input)
            current = await repository.get_path(path_input.slug)
            section_names = {section.title for section in current.sections}
            for title, icon, article_slugs in definition["sections"]:
                if title not in section_names:
                    await repository.add_section(
                        path_input.slug,
                        LearningPathSectionInput(title=title, icon=icon),
                    )
                current = await repository.get_path(path_input.slug)
                existing_lessons = {
                    lesson.article.slug
                    for section in current.sections
                    for lesson in section.lessons
                }
                for article_slug in article_slugs:
                    if article_slug not in existing_lessons:
                        await repository.add_lesson(
                            path_input.slug,
                            title,
                            LearningPathLessonInput(article_slug=article_slug),
                        )
                        existing_lessons.add(article_slug)


if __name__ == "__main__":
    asyncio.run(seed())
