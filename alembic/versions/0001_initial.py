"""Initial persistence model."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("character_profiles",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(200), nullable=False),
        sa.Column("build_stage", sa.String(50), nullable=False), sa.Column("life", sa.Integer()),
        sa.Column("energy_shield", sa.Integer()), sa.Column("mana", sa.Integer()), sa.Column("spirit", sa.Integer()),
        sa.Column("strength", sa.Integer()), sa.Column("dexterity", sa.Integer()), sa.Column("intelligence", sa.Integer()),
        sa.Column("fire_resistance", sa.Integer()), sa.Column("cold_resistance", sa.Integer()),
        sa.Column("lightning_resistance", sa.Integer()), sa.Column("chaos_resistance", sa.Integer()),
        sa.Column("resistance_cap", sa.Integer(), nullable=False), sa.Column("notes", sa.Text(), nullable=False))
    op.create_table("items",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("unknown_lines", sa.JSON(), nullable=False), sa.Column("item_class", sa.String(100)),
        sa.Column("rarity", sa.String(30)), sa.Column("name", sa.String(200)), sa.Column("base_type", sa.String(200)),
        sa.Column("required_level", sa.Integer()), sa.Column("required_strength", sa.Integer()),
        sa.Column("required_dexterity", sa.Integer()), sa.Column("required_intelligence", sa.Integer()),
        sa.Column("item_level", sa.Integer()), sa.Column("quality", sa.Integer()), sa.Column("sockets", sa.JSON(), nullable=False),
        sa.Column("armour", sa.Integer()), sa.Column("armour_augmented", sa.Boolean(), nullable=False),
        sa.Column("evasion", sa.Integer()), sa.Column("evasion_augmented", sa.Boolean(), nullable=False),
        sa.Column("energy_shield", sa.Integer()), sa.Column("energy_shield_augmented", sa.Boolean(), nullable=False),
        sa.Column("spirit", sa.Integer()), sa.Column("granted_skill", sa.String(300)),
        sa.Column("identified", sa.Boolean(), nullable=False), sa.Column("corrupted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("modifiers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False), sa.Column("affix_type", sa.String(20)),
        sa.Column("name", sa.String(200)), sa.Column("tier", sa.Integer()), sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("normalized_key", sa.String(100), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False), sa.Column("roll_ranges", sa.JSON(), nullable=False),
        sa.Column("crafted", sa.Boolean(), nullable=False), sa.Column("desecrated", sa.Boolean(), nullable=False),
        sa.Column("rune", sa.Boolean(), nullable=False), sa.Column("implicit", sa.Boolean(), nullable=False),
        sa.Column("unique", sa.Boolean(), nullable=False))
    op.create_index("ix_modifiers_item_id", "modifiers", ["item_id"])
    op.create_table("equipment_slots",
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("character_profiles.id"), primary_key=True),
        sa.Column("slot", sa.String(30), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False, unique=True))
    op.create_table("evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("character_profiles.id"), nullable=False),
        sa.Column("target_slot", sa.String(30)), sa.Column("build_fit_score", sa.Integer()),
        sa.Column("equipped_item_score", sa.Integer()), sa.Column("score_delta", sa.Integer()),
        sa.Column("upgrade_recommendation", sa.String(50)), sa.Column("trade_potential_score", sa.Integer()),
        sa.Column("trade_recommendation", sa.String(50)), sa.Column("confidence", sa.String(20)),
        sa.Column("reasons", sa.JSON(), nullable=False), sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_evaluations_item_id", "evaluations", ["item_id"])
    op.create_index("ix_evaluations_character_id", "evaluations", ["character_id"])
    op.create_table("sale_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("listed_at", sa.DateTime(timezone=True)), sa.Column("listed_currency", sa.String(50)),
        sa.Column("listed_amount", sa.Numeric(18, 4)), sa.Column("sold_at", sa.DateTime(timezone=True)),
        sa.Column("sold_currency", sa.String(50)), sa.Column("sold_amount", sa.Numeric(18, 4)),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("notes", sa.Text(), nullable=False))
    op.create_index("ix_sale_records_item_id", "sale_records", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_sale_records_item_id", table_name="sale_records")
    op.drop_table("sale_records")
    op.drop_index("ix_evaluations_character_id", table_name="evaluations")
    op.drop_index("ix_evaluations_item_id", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_table("equipment_slots")
    op.drop_index("ix_modifiers_item_id", table_name="modifiers")
    op.drop_table("modifiers")
    op.drop_table("items")
    op.drop_table("character_profiles")
