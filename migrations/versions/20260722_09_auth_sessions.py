"""Link reader profiles to Supabase identities and add device sessions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_09"
down_revision: str | None = "20260722_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add authenticated ownership without deleting anonymous reader data."""
    op.add_column(
        "reader_profiles", sa.Column("auth_user_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "reader_profiles", sa.Column("display_name", sa.String(80), nullable=True)
    )
    op.add_column(
        "reader_profiles", sa.Column("avatar_url", sa.String(500), nullable=True)
    )
    op.add_column(
        "reader_profiles",
        sa.Column("app_role", sa.String(20), server_default="reader", nullable=False),
    )
    op.add_column(
        "reader_profiles",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_reader_profile_role",
        "reader_profiles",
        "app_role IN ('reader', 'admin')",
    )
    op.create_unique_constraint(
        "uq_reader_profiles_auth_user_id", "reader_profiles", ["auth_user_id"]
    )
    op.create_foreign_key(
        "fk_reader_profiles_auth_user_id",
        "reader_profiles",
        "users",
        ["auth_user_id"],
        ["id"],
        source_schema=None,
        referent_schema="auth",
        ondelete="CASCADE",
    )

    op.create_table(
        "user_sessions",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("auth_user_id", sa.Uuid(), nullable=False),
        sa.Column("reader_id", sa.Uuid(), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("device_label", sa.String(100), nullable=True),
        sa.Column("ip_prefix_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(40), nullable=True),
        sa.Column("csrf_token_hash", sa.String(64), nullable=False),
        sa.CheckConstraint("expires_at > created_at", name="ck_user_session_expiry"),
        sa.ForeignKeyConstraint(
            ["auth_user_id"], ["auth.users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reader_id"], ["reader_profiles.reader_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        "ix_user_sessions_owner_activity",
        "user_sessions",
        ["auth_user_id", "revoked_at", sa.text("last_seen_at DESC")],
    )
    op.create_index("ix_user_sessions_reader_id", "user_sessions", ["reader_id"])

    op.create_table(
        "security_events",
        sa.Column(
            "event_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("auth_user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("ip_prefix_hash", sa.String(64), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["auth_user_id"], ["auth.users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["user_sessions.session_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_security_events_owner_time",
        "security_events",
        ["auth_user_id", sa.text("occurred_at DESC")],
    )


def downgrade() -> None:
    """Remove authentication metadata while retaining reader content."""
    op.drop_table("security_events")
    op.drop_table("user_sessions")
    op.drop_constraint(
        "fk_reader_profiles_auth_user_id", "reader_profiles", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_reader_profiles_auth_user_id", "reader_profiles", type_="unique"
    )
    op.drop_constraint("ck_reader_profile_role", "reader_profiles", type_="check")
    op.drop_column("reader_profiles", "created_at")
    op.drop_column("reader_profiles", "app_role")
    op.drop_column("reader_profiles", "avatar_url")
    op.drop_column("reader_profiles", "display_name")
    op.drop_column("reader_profiles", "auth_user_id")
