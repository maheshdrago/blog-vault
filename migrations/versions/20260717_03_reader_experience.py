"""Add reading appearance preferences and recent-read timestamps."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_03"
down_revision: str | None = "20260717_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add reader typography settings and explicit reading recency."""
    op.add_column(
        "reader_profiles",
        sa.Column(
            "font_family",
            sa.String(length=10),
            nullable=False,
            server_default="serif",
        ),
    )
    op.add_column(
        "reader_profiles",
        sa.Column(
            "line_height",
            sa.Integer(),
            nullable=False,
            server_default="180",
        ),
    )
    op.add_column(
        "reader_profiles",
        sa.Column(
            "content_width",
            sa.Integer(),
            nullable=False,
            server_default="760",
        ),
    )
    op.add_column(
        "reading_states",
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove reading appearance and recency fields."""
    op.drop_column("reading_states", "last_read_at")
    op.drop_column("reader_profiles", "content_width")
    op.drop_column("reader_profiles", "line_height")
    op.drop_column("reader_profiles", "font_family")
