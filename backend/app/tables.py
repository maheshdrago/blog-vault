"""SQLAlchemy mappings for articles and persistent reader state."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative database mapping base."""


class ArticleTable(Base):
    """The single mutable working copy and workflow state for an article."""

    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_review', 'changes_requested', 'approved', "
            "'published', 'archived')",
            name="ck_articles_status",
        ),
    )

    article_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    publication_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    cover: Mapped[str] = mapped_column(String(500), nullable=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reading_html: Mapped[str] = mapped_column(Text, nullable=False)
    experience_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_sources: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    revision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    review_cycle_id: Mapped[UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )
    submitted_content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ArticleSnapshotTable(Base):
    """The one last-known-good published snapshot available for rollback."""

    __tablename__ = "article_snapshots"
    article_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.article_id", ondelete="CASCADE"),
        primary_key=True,
    )
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    publication_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    cover: Mapped[str] = mapped_column(String(500), nullable=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reading_html: Mapped[str] = mapped_column(Text, nullable=False)
    experience_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_sources: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ArticleReviewCommentTable(Base):
    """Feedback and replies scoped to one article review cycle."""

    __tablename__ = "article_review_comments"
    __table_args__ = (
        CheckConstraint(
            "author IN ('human', 'assistant')",
            name="ck_article_review_comments_author",
        ),
        CheckConstraint(
            "anchor_type IN ('general', 'section', 'figure')",
            name="ck_article_review_comments_anchor_type",
        ),
        CheckConstraint(
            "status IN ('open', 'addressed', 'resolved')",
            name="ck_article_review_comments_status",
        ),
    )

    comment_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    article_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.article_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_cycle_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    parent_comment_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("article_review_comments.comment_id", ondelete="CASCADE"),
        nullable=True,
    )
    author: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    anchor_value: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LearningPathTable(Base):
    """A curated, ordered curriculum exposed to readers and MCP clients."""

    __tablename__ = "learning_paths"

    path_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    icon: Mapped[str] = mapped_column(String(30), default="book", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningPathSectionTable(Base):
    """A named category grouping related lessons within a learning path."""

    __tablename__ = "learning_path_sections"
    __table_args__ = (
        UniqueConstraint("path_id", "title", name="uq_learning_path_section_title"),
    )

    section_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    path_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("learning_paths.path_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[str] = mapped_column(String(30), default="book", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LearningPathLessonTable(Base):
    """An article's ordered placement inside one curriculum section."""

    __tablename__ = "learning_path_lessons"
    __table_args__ = (
        UniqueConstraint("path_id", "article_id", name="uq_learning_path_article"),
        UniqueConstraint(
            "section_id", "sort_order", name="uq_learning_path_lesson_order"
        ),
    )

    lesson_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    path_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("learning_paths.path_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("learning_path_sections.section_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("articles.article_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ReaderProfileTable(Base):
    """Anonymous reader preferences identified by a browser-generated UUID."""

    __tablename__ = "reader_profiles"

    reader_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    theme: Mapped[str] = mapped_column(String(10), default="dark")
    font_scale: Mapped[int] = mapped_column(Integer, default=100)
    font_family: Mapped[str] = mapped_column(String(10), default="serif")
    line_height: Mapped[int] = mapped_column(Integer, default=180)
    content_width: Mapped[int] = mapped_column(Integer, default=760)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReadingStateTable(Base):
    """Per-post state belonging to an anonymous reader profile."""

    __tablename__ = "reading_states"

    reader_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("reader_profiles.reader_id", ondelete="CASCADE"),
        primary_key=True,
    )
    post_slug: Mapped[str] = mapped_column(String(160), primary_key=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    group_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("reader_groups.group_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReaderGroupTable(Base):
    """Named personal collection used to organize blog posts."""

    __tablename__ = "reader_groups"
    __table_args__ = (
        UniqueConstraint("reader_id", "name", name="uq_reader_group_name"),
    )

    group_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    reader_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("reader_profiles.reader_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#8873ef")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
