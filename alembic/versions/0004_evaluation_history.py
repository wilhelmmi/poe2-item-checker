"""Persist local evaluation snapshots and history metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0004_evaluation_history"
down_revision = "0003_explicit_empty_equipment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    duplicate = op.get_bind().execute(sa.text(
        "SELECT item_id FROM sale_records GROUP BY item_id HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError(
            "Migration 0004 cannot continue: duplicate sale_records exist for an item; "
            "merge them manually before retrying."
        )
    op.create_index("ux_sale_records_item_id", "sale_records", ["item_id"], unique=True)
    with op.batch_alter_table("evaluations") as batch:
        batch.add_column(sa.Column("completeness", sa.String(20), nullable=True))
        batch.add_column(sa.Column("rule_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="checked"))
        batch.add_column(sa.Column("local_category", sa.String(50), nullable=True))
        batch.add_column(sa.Column("local_delta_band", sa.String(30), nullable=True))
        batch.add_column(sa.Column("snapshot", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("parent_evaluation_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                                   server_default=sa.func.current_timestamp()))
        batch.create_foreign_key("fk_evaluations_parent", "evaluations", ["parent_evaluation_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_evaluations_parent_evaluation_id", ["parent_evaluation_id"])


def downgrade() -> None:
    with op.batch_alter_table("evaluations") as batch:
        batch.drop_index("ix_evaluations_parent_evaluation_id")
        batch.drop_constraint("fk_evaluations_parent", type_="foreignkey")
        for column in ("updated_at", "parent_evaluation_id", "snapshot", "local_delta_band",
                       "local_category", "status", "rule_version", "completeness"):
            batch.drop_column(column)
    op.drop_index("ux_sale_records_item_id", table_name="sale_records")
