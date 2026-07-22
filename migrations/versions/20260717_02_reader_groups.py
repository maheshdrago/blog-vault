"""Add personal groups for organizing blog posts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_02"
down_revision: str | None = "20260717_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create groups and add optional group membership to reading states."""
    op.create_table(
        "reader_groups",
        sa.Column(
            "group_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("reader_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["reader_id"], ["reader_profiles.reader_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("group_id"),
        sa.UniqueConstraint("reader_id", "name", name="uq_reader_group_name"),
    )
    op.create_index("ix_reader_groups_reader_id", "reader_groups", ["reader_id"])
    op.add_column("reading_states", sa.Column("group_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_reading_states_group_id",
        "reading_states",
        "reader_groups",
        ["group_id"],
        ["group_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove personal group storage."""
    op.drop_constraint(
        "fk_reading_states_group_id", "reading_states", type_="foreignkey"
    )
    op.drop_column("reading_states", "group_id")
    op.drop_index("ix_reader_groups_reader_id", table_name="reader_groups")
    op.drop_table("reader_groups")
