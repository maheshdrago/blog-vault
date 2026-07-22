"""Create reader preference and reading state tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tables for anonymous reader persistence."""
    op.create_table(
        "reader_profiles",
        sa.Column("reader_id", sa.Uuid(), nullable=False),
        sa.Column("theme", sa.String(length=10), nullable=False),
        sa.Column("font_scale", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("reader_id"),
    )
    op.create_table(
        "reading_states",
        sa.Column("reader_id", sa.Uuid(), nullable=False),
        sa.Column("post_slug", sa.String(length=160), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("is_bookmarked", sa.Boolean(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reader_id"],
            ["reader_profiles.reader_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("reader_id", "post_slug"),
        sa.CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name="ck_progress_percent",
        ),
    )


def downgrade() -> None:
    """Drop reader persistence tables."""
    op.drop_table("reading_states")
    op.drop_table("reader_profiles")
