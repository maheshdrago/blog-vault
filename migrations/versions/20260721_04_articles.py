"""Add versioned database-backed article storage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_04"
down_revision: str | None = "20260717_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create article identities, immutable versions, and publication pointer."""
    op.create_table(
        "articles",
        sa.Column(
            "article_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("published_version_id", sa.Uuid(), nullable=True),
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
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'published', 'archived')",
            name="ck_articles_status",
        ),
        sa.PrimaryKeyConstraint("article_id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "article_versions",
        sa.Column(
            "version_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("cover", sa.String(length=500), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("reading_html", sa.Text(), nullable=False),
        sa.Column("experience_html", sa.Text(), nullable=True),
        sa.Column("research_sources", sa.JSON(), nullable=False),
        sa.Column("revision_notes", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'published', 'superseded', 'rejected')",
            name="ck_article_versions_status",
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles.article_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("version_id"),
        sa.UniqueConstraint(
            "article_id", "content_hash", name="uq_article_version_content"
        ),
        sa.UniqueConstraint(
            "article_id", "version_number", name="uq_article_version_number"
        ),
    )
    op.create_index(
        "ix_article_versions_article_id",
        "article_versions",
        ["article_id"],
    )
    op.create_foreign_key(
        "fk_articles_published_version_id",
        "articles",
        "article_versions",
        ["published_version_id"],
        ["version_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove database-backed article storage."""
    op.drop_constraint(
        "fk_articles_published_version_id", "articles", type_="foreignkey"
    )
    op.drop_index("ix_article_versions_article_id", table_name="article_versions")
    op.drop_table("article_versions")
    op.drop_table("articles")
