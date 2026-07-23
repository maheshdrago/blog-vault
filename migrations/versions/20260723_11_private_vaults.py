"""Make articles private per user and add personal MCP credentials."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_11"
down_revision: str | None = "20260723_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add owner boundaries while leaving legacy content for first-account claim."""
    op.add_column("articles", sa.Column("owner_reader_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_articles_owner_reader_id",
        "articles",
        "reader_profiles",
        ["owner_reader_id"],
        ["reader_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_articles_owner_reader_id", "articles", ["owner_reader_id"])
    op.drop_constraint("articles_slug_key", "articles", type_="unique")
    op.create_unique_constraint(
        "uq_articles_owner_slug", "articles", ["owner_reader_id", "slug"]
    )

    op.add_column(
        "learning_paths", sa.Column("owner_reader_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_learning_paths_owner_reader_id",
        "learning_paths",
        "reader_profiles",
        ["owner_reader_id"],
        ["reader_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_learning_paths_owner_reader_id",
        "learning_paths",
        ["owner_reader_id"],
    )
    op.drop_constraint("learning_paths_slug_key", "learning_paths", type_="unique")
    op.create_unique_constraint(
        "uq_learning_paths_owner_slug",
        "learning_paths",
        ["owner_reader_id", "slug"],
    )

    op.drop_table("local_state_imports")
    op.execute("DELETE FROM reader_profiles WHERE auth_user_id IS NULL")

    op.create_table(
        "mcp_credentials",
        sa.Column(
            "credential_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("reader_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["reader_id"], ["reader_profiles.reader_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("credential_id"),
        sa.UniqueConstraint("token_hash", name="uq_mcp_credentials_token_hash"),
    )
    op.create_index("ix_mcp_credentials_reader_id", "mcp_credentials", ["reader_id"])


def downgrade() -> None:
    """Restore global slugs and the former local-import receipt table."""
    op.drop_table("mcp_credentials")

    op.drop_constraint("uq_learning_paths_owner_slug", "learning_paths", type_="unique")
    op.drop_index("ix_learning_paths_owner_reader_id", table_name="learning_paths")
    op.drop_constraint(
        "fk_learning_paths_owner_reader_id", "learning_paths", type_="foreignkey"
    )
    op.drop_column("learning_paths", "owner_reader_id")
    op.create_unique_constraint("learning_paths_slug_key", "learning_paths", ["slug"])

    op.drop_constraint("uq_articles_owner_slug", "articles", type_="unique")
    op.drop_index("ix_articles_owner_reader_id", table_name="articles")
    op.drop_constraint("fk_articles_owner_reader_id", "articles", type_="foreignkey")
    op.drop_column("articles", "owner_reader_id")
    op.create_unique_constraint("articles_slug_key", "articles", ["slug"])

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
