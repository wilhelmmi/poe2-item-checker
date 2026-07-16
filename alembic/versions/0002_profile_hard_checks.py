"""Add profile fields needed for deterministic hard checks."""
from alembic import op
import sqlalchemy as sa

revision = "0002_profile_hard_checks"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("character_profiles", sa.Column("character_level", sa.Integer()))
    op.add_column("character_profiles", sa.Column("spirit_required", sa.Integer()))
    op.add_column("character_profiles", sa.Column("spirit_reserved", sa.Integer()))


def downgrade() -> None:
    op.drop_column("character_profiles", "spirit_reserved")
    op.drop_column("character_profiles", "spirit_required")
    op.drop_column("character_profiles", "character_level")
