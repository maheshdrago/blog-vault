"""Pydantic request and response models for blog content."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from .articles.authoring_policy import validate_interactive_experience
from .articles.content_policy import INTERACTIVE_EXPERIENCE_PATH_PATTERN


def to_camel(value: str) -> str:
    """Convert a snake_case field name to lower camelCase."""
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    """Base API model with camelCase JSON serialization."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ArticleInputBase(ApiModel):
    """Metadata shared by semantic and interactive article inputs."""

    title: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    date: date
    description: str = Field(
        min_length=1,
        max_length=240,
        description="Specific UI summary; target 140–220 characters.",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Lowercase, stable subject tags; target three to six.",
    )
    cover: str = "/assets/architecture-cover.png"
    featured: bool = False

    @field_validator("title", "description", "cover")
    @classmethod
    def validate_metadata_line(cls, value: str) -> str:
        """Reject line breaks that could inject additional metadata fields."""
        if "\n" in value or "\r" in value:
            raise ValueError("Metadata values must fit on one line.")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        """Normalize tags and reject empty or excessively long values."""
        normalized = [tag.strip().lower() for tag in tags]
        if any(
            not tag or len(tag) > 30 or "\n" in tag or "\r" in tag for tag in normalized
        ):
            raise ValueError("Tags must contain between 1 and 30 characters.")
        return list(dict.fromkeys(normalized))


class PostInput(ArticleInputBase):
    """Validated semantic post used to create or replace a draft."""

    experience: str | None = Field(
        default=None, pattern=INTERACTIVE_EXPERIENCE_PATH_PATTERN
    )
    html: str = Field(min_length=1)


class ResearchSource(ApiModel):
    """A checked source and the article claim it supports."""

    publisher: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    url: HttpUrl
    claim_supported: str = Field(min_length=10, max_length=500)


class InteractivePostInput(ArticleInputBase):
    """Research-backed post with semantic and animated representations."""

    html: str = Field(min_length=1)
    experience_html: str = Field(min_length=500, max_length=500_000)
    research_sources: list[ResearchSource] = Field(min_length=3, max_length=12)

    @field_validator("experience_html")
    @classmethod
    def validate_experience_html(cls, value: str) -> str:
        """Enforce theming, structure, accessibility, and sandbox boundaries."""
        validate_interactive_experience(value)
        return value.strip()

    @field_validator("research_sources")
    @classmethod
    def validate_independent_sources(
        cls, sources: list[ResearchSource]
    ) -> list[ResearchSource]:
        """Require distinct URLs and at least three independent publishers."""
        urls = [str(source.url) for source in sources]
        if len(set(urls)) != len(urls):
            raise ValueError("Research source URLs must be unique.")
        hosts = {source.url.host for source in sources}
        if len(hosts) < 3:
            raise ValueError(
                "Research must include at least three independent source hosts."
            )
        return sources

    def to_post_input(self) -> PostInput:
        """Build canonical metadata with its database-backed experience path."""
        values = self.model_dump(exclude={"experience_html", "research_sources"})
        return PostInput(
            **values,
            experience=f"/posts/{self.slug}/experience",
        )


class Post(PostInput):
    """Complete post returned to API and MCP consumers."""

    reading_time: int = Field(ge=1)


class PostSummary(ApiModel):
    """Post metadata returned by list and search operations."""

    title: str
    slug: str
    date: date
    description: str
    tags: list[str]
    cover: str
    experience: str | None = None
    featured: bool
    reading_time: int


class ArticleWorkflowStatus(StrEnum):
    """Workflow states for the single working article copy."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ArticleRecord(ApiModel):
    """Identity and workflow metadata for a working article."""

    article_id: UUID
    slug: str
    status: ArticleWorkflowStatus
    review_cycle_id: UUID | None = None
    submitted_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None


class ArticleDetail(ArticleRecord):
    """The complete current working copy used for review and MCP updates."""

    post: Post
    experience_html: str | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    research_sources: list[ResearchSource] = Field(default_factory=list)
    revision_notes: str | None = None


class ArticleSnapshot(ApiModel):
    """The one previous published copy retained for public reads and rollback."""

    article_id: UUID
    slug: str
    post: Post
    experience_html: str | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    research_sources: list[ResearchSource] = Field(default_factory=list)
    captured_at: datetime
    published_at: datetime


class ReviewAnchorType(StrEnum):
    """Stable article locations to which human feedback can be attached."""

    GENERAL = "general"
    SECTION = "section"
    FIGURE = "figure"


class ReviewCommentStatus(StrEnum):
    """Resolution state controlled by the reviewer and revising assistant."""

    OPEN = "open"
    ADDRESSED = "addressed"
    RESOLVED = "resolved"


class ReviewCommentAuthor(StrEnum):
    """Trusted actor that wrote one persisted review message."""

    HUMAN = "human"
    ASSISTANT = "assistant"


class ArticleReviewCommentInput(ApiModel):
    """Human feedback attached to an active article review cycle."""

    body: str = Field(min_length=1, max_length=4_000)
    anchor_type: ReviewAnchorType = ReviewAnchorType.GENERAL
    anchor_value: str | None = Field(default=None, max_length=240)

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        """Trim feedback while retaining intentional internal line breaks."""
        return value.strip()

    @model_validator(mode="after")
    def validate_anchor(self) -> "ArticleReviewCommentInput":
        """Require a concrete identifier for section and figure comments."""
        if self.anchor_type is ReviewAnchorType.GENERAL:
            self.anchor_value = None
        elif not self.anchor_value or not self.anchor_value.strip():
            raise ValueError("Section and figure comments require an anchor value.")
        else:
            self.anchor_value = self.anchor_value.strip()
        return self


class ArticleReviewReplyInput(ApiModel):
    """Assistant response explaining how one review comment was addressed."""

    body: str = Field(min_length=1, max_length=4_000)

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        """Reject whitespace-only assistant responses."""
        return value.strip()


class ArticleReviewResolutionInput(ApiModel):
    """Human decision to resolve or reopen a root review comment."""

    resolved: bool


class ArticleReviewComment(ApiModel):
    """One persisted human comment or assistant reply."""

    comment_id: UUID
    article_id: UUID
    review_cycle_id: UUID
    parent_comment_id: UUID | None = None
    author: ReviewCommentAuthor
    body: str
    anchor_type: ReviewAnchorType
    anchor_value: str | None = None
    status: ReviewCommentStatus
    created_at: datetime
    resolved_at: datetime | None = None


class ArticleReviewQueueItem(ArticleRecord):
    """Compact review-inbox entry with actionable feedback counts."""

    title: str
    description: str
    open_comments: int = Field(ge=0)
    addressed_comments: int = Field(ge=0)


class ArticleReviewContext(ApiModel):
    """Working article, private rollback snapshot, and review feedback."""

    article: ArticleDetail
    published_snapshot: ArticleSnapshot | None = None
    comments: list[ArticleReviewComment] = Field(default_factory=list)


class LearningPathInput(ApiModel):
    """Validated metadata for a curated learning sequence."""

    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    icon: str = Field(default="book", min_length=1, max_length=30)


class LearningPathSectionInput(ApiModel):
    """A named category to append to a learning path."""

    title: str = Field(min_length=1, max_length=120)
    icon: str = Field(default="book", min_length=1, max_length=30)


class LearningPathLessonInput(ApiModel):
    """An article placement inside a path category."""

    article_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    is_required: bool = True


class LearningPathLesson(ApiModel):
    """A curriculum lesson enriched with reader progress and lock state."""

    lesson_id: UUID
    article: PostSummary
    sort_order: int = Field(ge=0)
    is_required: bool
    progress_percent: int = Field(ge=0, le=100)
    is_completed: bool
    is_locked: bool


class LearningPathSection(ApiModel):
    """An ordered curriculum category and its lessons."""

    section_id: UUID
    title: str
    icon: str
    sort_order: int = Field(ge=0)
    lessons: list[LearningPathLesson] = Field(default_factory=list)


class LearningPath(ApiModel):
    """A complete curated path with reader-specific aggregate progress."""

    path_id: UUID
    slug: str
    title: str
    description: str
    icon: str
    sort_order: int = Field(ge=0)
    completed_lessons: int = Field(ge=0)
    total_lessons: int = Field(ge=0)
    progress_percent: int = Field(ge=0, le=100)
    sections: list[LearningPathSection] = Field(default_factory=list)


class HealthResponse(ApiModel):
    """Service health response."""

    status: str
    database_configured: bool
    telemetry_configured: bool
    authentication_configured: bool


class ReaderPreferencesInput(ApiModel):
    """Mutable display preferences associated with one reader profile."""

    theme: str = Field(default="dark", pattern=r"^(dark|light|system)$")
    font_scale: int = Field(default=100, ge=80, le=150)
    font_family: str = Field(default="serif", pattern=r"^(serif|sans)$")
    line_height: int = Field(default=180, ge=140, le=220)
    content_width: int = Field(default=760, ge=560, le=920)


class ReaderPreferences(ReaderPreferencesInput):
    """Persisted reader preferences."""

    reader_id: UUID
    updated_at: datetime


class ReadingStateInput(ApiModel):
    """Mutable reading state for one reader and post."""

    is_favorite: bool = False
    is_bookmarked: bool = False
    progress_percent: int = Field(default=0, ge=0, le=100)
    group_id: UUID | None = None


class ReadingState(ReadingStateInput):
    """Persisted reading state for one reader and post."""

    reader_id: UUID
    post_slug: str
    updated_at: datetime
    last_read_at: datetime | None = None


class ReaderGroupInput(ApiModel):
    """Mutable fields used to create or rename a reader collection."""

    name: str = Field(min_length=1, max_length=50)
    color: str = Field(default="#8873ef", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Trim collection names and reject control characters."""
        normalized = value.strip()
        if any(character in normalized for character in "\r\n\t"):
            raise ValueError("Group names must fit on one line.")
        return normalized


class ReaderGroup(ReaderGroupInput):
    """Persisted personal collection of blog posts."""

    group_id: UUID
    reader_id: UUID
    created_at: datetime
    updated_at: datetime
