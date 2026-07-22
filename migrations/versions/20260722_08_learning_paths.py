"""Add curated learning paths, categories, and ordered article lessons."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_08"
down_revision: str | None = "20260722_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the normalized curriculum structure."""
    op.create_table(
        "learning_paths",
        sa.Column(
            "path_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("icon", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("path_id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "learning_path_sections",
        sa.Column(
            "section_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("icon", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["path_id"], ["learning_paths.path_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("section_id"),
        sa.UniqueConstraint("path_id", "title", name="uq_learning_path_section_title"),
    )
    op.create_index(
        "ix_learning_path_sections_path_id", "learning_path_sections", ["path_id"]
    )
    op.create_table(
        "learning_path_lessons",
        sa.Column(
            "lesson_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["path_id"], ["learning_paths.path_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["section_id"], ["learning_path_sections.section_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles.article_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("lesson_id"),
        sa.UniqueConstraint("path_id", "article_id", name="uq_learning_path_article"),
        sa.UniqueConstraint(
            "section_id", "sort_order", name="uq_learning_path_lesson_order"
        ),
    )
    op.create_index(
        "ix_learning_path_lessons_path_id", "learning_path_lessons", ["path_id"]
    )
    op.create_index(
        "ix_learning_path_lessons_section_id",
        "learning_path_lessons",
        ["section_id"],
    )
    op.create_index(
        "ix_learning_path_lessons_article_id",
        "learning_path_lessons",
        ["article_id"],
    )


def downgrade() -> None:
    """Remove curriculum storage without touching articles or reader progress."""
    op.drop_table("learning_path_lessons")
    op.drop_table("learning_path_sections")
    op.drop_table("learning_paths")
