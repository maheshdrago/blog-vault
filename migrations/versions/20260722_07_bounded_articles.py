"""Collapse article history into one working copy and one published snapshot."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260722_07"
down_revision: str | None = "20260721_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate the latest useful copies, then remove unbounded version storage."""
    op.drop_constraint("ck_articles_status", "articles", type_="check")
    op.create_check_constraint(
        "ck_articles_status",
        "articles",
        "status IN ('draft', 'in_review', 'changes_requested', 'approved', "
        "'published', 'archived')",
    )
    for column in (
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(length=240), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("cover", sa.String(length=500), nullable=True),
        sa.Column("featured", sa.Boolean(), nullable=True),
        sa.Column("reading_html", sa.Text(), nullable=True),
        sa.Column("experience_html", sa.Text(), nullable=True),
        sa.Column("research_sources", sa.JSON(), nullable=True),
        sa.Column("revision_notes", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("review_cycle_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_content_hash", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("articles", column)
    op.create_index("ix_articles_review_cycle_id", "articles", ["review_cycle_id"])

    op.create_table(
        "article_snapshots",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("cover", sa.String(length=500), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("reading_html", sa.Text(), nullable=False),
        sa.Column("experience_html", sa.Text(), nullable=True),
        sa.Column("research_sources", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles.article_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("article_id"),
    )

    op.add_column(
        "article_review_comments",
        sa.Column("article_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "article_review_comments",
        sa.Column("review_cycle_id", sa.Uuid(), nullable=True),
    )

    op.execute(
        """
        WITH working AS (
            SELECT
                a.article_id,
                COALESCE(active.version_id, published.version_id, latest.version_id)
                    AS version_id
            FROM articles AS a
            LEFT JOIN LATERAL (
                SELECT av.version_id
                FROM article_versions AS av
                WHERE av.article_id = a.article_id
                  AND av.status IN (
                    'draft', 'in_review', 'changes_requested', 'approved'
                  )
                ORDER BY av.version_number DESC
                LIMIT 1
            ) AS active ON TRUE
            LEFT JOIN article_versions AS published
              ON published.version_id = a.published_version_id
            LEFT JOIN LATERAL (
                SELECT av.version_id
                FROM article_versions AS av
                WHERE av.article_id = a.article_id
                ORDER BY av.version_number DESC
                LIMIT 1
            ) AS latest ON TRUE
        )
        UPDATE articles AS a
        SET
            status = CASE
                WHEN v.status IN (
                    'draft', 'in_review', 'changes_requested', 'approved', 'published'
                ) THEN v.status
                ELSE 'draft'
            END,
            title = v.title,
            publication_date = v.publication_date,
            description = v.description,
            tags = v.tags,
            cover = v.cover,
            featured = v.featured,
            reading_html = v.reading_html,
            experience_html = v.experience_html,
            research_sources = v.research_sources,
            revision_notes = v.revision_notes,
            content_hash = v.content_hash,
            review_cycle_id = CASE
                WHEN v.status IN ('in_review', 'changes_requested', 'approved')
                  OR EXISTS (
                    SELECT 1 FROM article_review_comments AS c
                    JOIN article_versions AS cv ON cv.version_id = c.version_id
                    WHERE cv.article_id = a.article_id
                  )
                THEN gen_random_uuid()
                ELSE NULL
            END,
            submitted_content_hash = CASE
                WHEN v.status IN ('in_review', 'approved') THEN v.content_hash
                ELSE NULL
            END,
            reviewed_at = v.reviewed_at
        FROM working AS w
        JOIN article_versions AS v ON v.version_id = w.version_id
        WHERE a.article_id = w.article_id
        """
    )

    op.execute(
        """
        WITH working AS (
            SELECT a.article_id, v.version_id, v.version_number
            FROM articles AS a
            JOIN LATERAL (
                SELECT av.version_id, av.version_number
                FROM article_versions AS av
                WHERE av.article_id = a.article_id
                  AND av.content_hash = a.content_hash
                ORDER BY av.version_number DESC
                LIMIT 1
            ) AS v ON TRUE
        ), backup AS (
            SELECT
                a.article_id,
                COALESCE(
                    CASE
                        WHEN a.published_version_id <> w.version_id
                        THEN a.published_version_id
                    END,
                    prior.version_id
                ) AS version_id
            FROM articles AS a
            JOIN working AS w ON w.article_id = a.article_id
            LEFT JOIN LATERAL (
                SELECT av.version_id
                FROM article_versions AS av
                WHERE av.article_id = a.article_id
                  AND av.version_number < w.version_number
                  AND av.status IN ('published', 'superseded')
                ORDER BY av.version_number DESC
                LIMIT 1
            ) AS prior ON TRUE
        )
        INSERT INTO article_snapshots (
            article_id, slug, title, publication_date, description, tags, cover,
            featured, reading_html, experience_html, research_sources, content_hash,
            captured_at, published_at
        )
        SELECT
            a.article_id, a.slug, v.title, v.publication_date, v.description,
            v.tags, v.cover, v.featured, v.reading_html, v.experience_html,
            v.research_sources, v.content_hash, now(),
            COALESCE(a.published_at, v.created_at)
        FROM backup AS b
        JOIN articles AS a ON a.article_id = b.article_id
        JOIN article_versions AS v ON v.version_id = b.version_id
        WHERE b.version_id IS NOT NULL
        """
    )

    op.execute(
        """
        UPDATE article_review_comments AS c
        SET article_id = v.article_id,
            review_cycle_id = a.review_cycle_id
        FROM article_versions AS v
        JOIN articles AS a ON a.article_id = v.article_id
        WHERE c.version_id = v.version_id
        """
    )

    if not context.is_offline_mode():
        connection = op.get_bind()
        missing = connection.execute(
            sa.text(
                "SELECT count(*) FROM articles "
                "WHERE title IS NULL OR content_hash IS NULL"
            )
        ).scalar_one()
        if missing:
            raise RuntimeError(f"Cannot collapse {missing} articles without content.")

        orphaned_comments = connection.execute(
            sa.text(
                "SELECT count(*) FROM article_review_comments "
                "WHERE article_id IS NULL OR review_cycle_id IS NULL"
            )
        ).scalar_one()
        if orphaned_comments:
            raise RuntimeError(
                f"Cannot collapse {orphaned_comments} review comments without "
                "an article."
            )

    for column_name in (
        "title",
        "publication_date",
        "description",
        "tags",
        "cover",
        "featured",
        "reading_html",
        "research_sources",
        "content_hash",
    ):
        op.alter_column("articles", column_name, nullable=False)
    op.alter_column("article_review_comments", "article_id", nullable=False)
    op.alter_column("article_review_comments", "review_cycle_id", nullable=False)
    op.create_foreign_key(
        "fk_article_review_comments_article_id",
        "article_review_comments",
        "articles",
        ["article_id"],
        ["article_id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_article_review_comments_article_id",
        "article_review_comments",
        ["article_id"],
    )
    op.create_index(
        "ix_article_review_comments_review_cycle_id",
        "article_review_comments",
        ["review_cycle_id"],
    )

    op.drop_constraint(
        "article_review_comments_version_id_fkey",
        "article_review_comments",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_article_review_comments_version_id",
        table_name="article_review_comments",
    )
    op.drop_column("article_review_comments", "version_id")
    op.drop_constraint(
        "fk_articles_published_version_id", "articles", type_="foreignkey"
    )
    op.drop_column("articles", "published_version_id")

    # These browser-audit tables belonged to the removed Playwright workflow and
    # still reference article_versions, so they are removed with that feature.
    op.drop_table("article_quality_findings")
    op.drop_table("article_quality_runs")
    op.drop_table("article_versions")


def downgrade() -> None:
    """Refuse an unsafe downgrade after intentionally collapsing content history."""
    raise RuntimeError(
        "20260722_07 is irreversible: restore a database backup to recover full "
        "article version history."
    )
