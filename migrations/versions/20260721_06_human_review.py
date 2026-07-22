"""Add durable human review comments and explicit approval states."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_06"
down_revision: str | None = "20260721_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create comment threads and expand the immutable version lifecycle."""
    op.drop_constraint("ck_article_versions_status", "article_versions", type_="check")
    op.create_check_constraint(
        "ck_article_versions_status",
        "article_versions",
        "status IN ('draft', 'in_review', 'changes_requested', 'approved', "
        "'published', 'superseded', 'rejected')",
    )
    op.create_table(
        "article_review_comments",
        sa.Column(
            "comment_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("parent_comment_id", sa.Uuid(), nullable=True),
        sa.Column("author", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("anchor_type", sa.String(length=20), nullable=False),
        sa.Column("anchor_value", sa.String(length=240), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "author IN ('human', 'assistant')",
            name="ck_article_review_comments_author",
        ),
        sa.CheckConstraint(
            "anchor_type IN ('general', 'section', 'figure')",
            name="ck_article_review_comments_anchor_type",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'addressed', 'resolved')",
            name="ck_article_review_comments_status",
        ),
        sa.ForeignKeyConstraint(
            ["parent_comment_id"],
            ["article_review_comments.comment_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["article_versions.version_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("comment_id"),
    )
    op.create_index(
        "ix_article_review_comments_version_id",
        "article_review_comments",
        ["version_id"],
    )


def downgrade() -> None:
    """Remove review comments and restore the earlier version lifecycle."""
    op.drop_index(
        "ix_article_review_comments_version_id",
        table_name="article_review_comments",
    )
    op.drop_table("article_review_comments")
    op.execute(
        "UPDATE article_versions SET status = 'in_review' "
        "WHERE status IN ('changes_requested', 'approved')"
    )
    op.drop_constraint("ck_article_versions_status", "article_versions", type_="check")
    op.create_check_constraint(
        "ck_article_versions_status",
        "article_versions",
        "status IN ('draft', 'in_review', 'published', 'superseded', 'rejected')",
    )
