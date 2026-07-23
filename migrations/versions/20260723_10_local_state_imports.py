"""Track idempotent imports of browser-local reading state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_10"
down_revision: str | None = "20260722_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the bounded receipt table for authenticated local imports."""
    op.create_table(
        "local_state_imports",
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("auth_user_id", sa.Uuid(), nullable=False),
        sa.Column("reader_id", sa.Uuid(), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["auth_user_id"], ["auth.users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reader_id"], ["reader_profiles.reader_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("import_id"),
    )
    op.create_index(
        "ix_local_state_imports_auth_user_id",
        "local_state_imports",
        ["auth_user_id"],
    )
    op.create_index(
        "ix_local_state_imports_reader_id",
        "local_state_imports",
        ["reader_id"],
    )


def downgrade() -> None:
    """Remove import receipts without changing reader content."""
    op.drop_table("local_state_imports")
