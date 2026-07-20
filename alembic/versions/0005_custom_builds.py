"""custom builds, previews, and preferences

Revision ID: 0005
Revises: 0004
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: str | None = "0004_evaluation_history"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("custom_builds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("build_id", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("author", sa.String(200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("source_variant", sa.String(200), nullable=False),
        sa.Column("archetype", sa.Text(), nullable=False),
        sa.Column("core_skills", sa.JSON(), nullable=False),
        sa.Column("offensive_priorities", sa.JSON(), nullable=False),
        sa.Column("defensive_priorities", sa.JSON(), nullable=False),
        sa.Column("item_priorities", sa.JSON(), nullable=False),
        sa.Column("low_value_stats", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("build_id"),
        sa.UniqueConstraint("source_url", "fingerprint", name="uq_custom_build_source_fingerprint"),
        sa.UniqueConstraint("source_url", "version", name="uq_custom_build_source_version"),
    )
    op.create_index("ix_custom_builds_build_id", "custom_builds", ["build_id"])
    op.create_table("build_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("analysis", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("confirmed_build_id", sa.String(120)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_build_previews_expires_at", "build_previews", ["expires_at"])
    op.create_table("app_preferences",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_preferences")
    op.drop_index("ix_build_previews_expires_at", table_name="build_previews")
    op.drop_table("build_previews")
    op.drop_index("ix_custom_builds_build_id", table_name="custom_builds")
    op.drop_table("custom_builds")
