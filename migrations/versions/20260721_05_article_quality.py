"""Add version-bound interactive article quality reports."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_05"
down_revision: str | None = "20260721_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create quality run and finding tables."""
    op.create_table(
        "article_quality_runs",
        sa.Column(
            "run_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("validator_version", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'passed', 'failed', 'error')",
            name="ck_article_quality_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["article_versions.version_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_article_quality_runs_version_id",
        "article_quality_runs",
        ["version_id"],
    )
    op.create_table(
        "article_quality_findings",
        sa.Column(
            "finding_id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=1_000), nullable=False),
        sa.Column("theme", sa.String(length=30), nullable=True),
        sa.Column("viewport", sa.String(length=30), nullable=True),
        sa.Column("selector", sa.String(length=500), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "severity IN ('error', 'warning', 'manual_review')",
            name="ck_article_quality_findings_severity",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["article_quality_runs.run_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("finding_id"),
    )
    op.create_index(
        "ix_article_quality_findings_run_id",
        "article_quality_findings",
        ["run_id"],
    )


def downgrade() -> None:
    """Remove article quality report storage."""
    op.drop_index(
        "ix_article_quality_findings_run_id",
        table_name="article_quality_findings",
    )
    op.drop_table("article_quality_findings")
    op.drop_index(
        "ix_article_quality_runs_version_id",
        table_name="article_quality_runs",
    )
    op.drop_table("article_quality_runs")
