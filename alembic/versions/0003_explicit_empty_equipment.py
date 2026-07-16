"""Represent an explicitly empty equipment slot."""
from alembic import op
import sqlalchemy as sa

revision = "0003_explicit_empty_equipment"
down_revision = "0002_profile_hard_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("equipment_slots") as batch:
        batch.alter_column("item_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM equipment_slots WHERE item_id IS NULL")
    with op.batch_alter_table("equipment_slots") as batch:
        batch.alter_column("item_id", existing_type=sa.String(36), nullable=False)
