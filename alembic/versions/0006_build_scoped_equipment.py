"""persist every build and scope equipment by build

Revision ID: 0006
Revises: 0005
"""
from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SOURCE = "https://mobalytics.gg/poe-2/builds/chaos-dot-lich-starter-deadrabbit?ws-ngf5-f7d82102-7e77-4a44-ad24-33b67e8ae7bf=activeVariantId%2Cdefault-variant"
_COMMON = {
    "name": "ED Contagion Chaos DoT Lich Starter", "author": "DEADRABB1T",
    "source_url": _SOURCE, "source_variant": "default-variant",
    "archetype": "Chaos damage over time Lich using Essence Drain and Contagion",
    "core_skills": ["Essence Drain", "Contagion", "Dark Effigy", "Despair"],
    "offensive_priorities": ["+ levels to Chaos Spell Skills", "Spell Damage and Chaos Damage", "Cast Speed is a useful bonus"],
    "defensive_priorities": ["high Energy Shield", "Energy Shield recharge", "elemental and chaos resistances"],
    "constraints": ["The build is mana hungry; account for mana sustain."], "citations": [],
}
_BUILTINS = (
    {**_COMMON, "id": "00000000-0000-4000-8000-000000000001", "build_id": "deadrabb1t-chaos-dot-lich-starter-v1", "version": 1,
     "item_priorities": [], "low_value_stats": []},
    {**_COMMON, "id": "00000000-0000-4000-8000-000000000002", "build_id": "deadrabb1t-chaos-dot-lich-starter-v2", "version": 2,
     "item_priorities": ["+ Level to all Chaos Spell Skills", "+ Level to all Spell Skills", "Spell Damage", "Chaos Damage", "Cast Speed", "Energy Shield", "Spirit", "Intelligence", "Elemental Resistances", "Chaos Resistance", "Movement Speed on Boots", "Mana and Mana Regeneration", "Maximum Life"],
     "low_value_stats": ["Attack Damage", "Accuracy", "Bleeding", "Physical Thorns", "Elemental Damage without Chaos DoT synergy", "Stun Threshold", "Evasion without further synergy"]},
)


def upgrade() -> None:
    op.rename_table("custom_builds", "builds")
    op.drop_index("ix_custom_builds_build_id", table_name="builds")
    op.create_index("ix_builds_build_id", "builds", ["build_id"])
    connection = op.get_bind()
    op.create_table("migration_0006_legacy_builds",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("old_build_id", sa.String(120), nullable=False),
        sa.Column("old_version", sa.Integer(), nullable=False), sa.Column("old_fingerprint", sa.String(64), nullable=False),
    )
    legacy_map = sa.table("migration_0006_legacy_builds", sa.column("id"), sa.column("old_build_id"), sa.column("old_version"), sa.column("old_fingerprint"))

    def remember(build_row_id: str) -> None:
        exists = connection.execute(sa.select(legacy_map.c.id).where(legacy_map.c.id == build_row_id)).scalar()
        if exists:
            return
        row = connection.execute(sa.text("SELECT id,build_id,version,fingerprint FROM builds WHERE id=:id"), {"id": build_row_id}).mappings().one()
        connection.execute(legacy_map.insert().values(id=row["id"], old_build_id=row["build_id"], old_version=row["version"], old_fingerprint=row["fingerprint"]))
    builds = sa.table("builds", *[
        sa.column("id", sa.String), sa.column("build_id", sa.String), sa.column("version", sa.Integer),
        sa.column("name", sa.String), sa.column("author", sa.String), sa.column("source_url", sa.Text),
        sa.column("fingerprint", sa.String), sa.column("source_variant", sa.String), sa.column("archetype", sa.Text),
        sa.column("core_skills", sa.JSON), sa.column("offensive_priorities", sa.JSON),
        sa.column("defensive_priorities", sa.JSON), sa.column("item_priorities", sa.JSON),
        sa.column("low_value_stats", sa.JSON), sa.column("constraints", sa.JSON), sa.column("citations", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
    ])
    now = datetime.now(timezone.utc)
    for builtin in _BUILTINS:
        collision = connection.execute(sa.text("SELECT id FROM builds WHERE build_id=:build_id"), builtin).scalar()
        if collision:
            remember(collision)
            legacy_id = f"{builtin['build_id']}-legacy-{collision}"
            connection.execute(sa.text("UPDATE build_previews SET confirmed_build_id=:new WHERE confirmed_build_id=:old"), {"new": legacy_id, "old": builtin["build_id"]})
            connection.execute(sa.text("UPDATE app_preferences SET value=:new WHERE key='active_build_id' AND value=:old"), {"new": legacy_id, "old": builtin["build_id"]})
            connection.execute(sa.text("UPDATE builds SET build_id=:new WHERE id=:id"), {"new": legacy_id, "id": collision})
        same_fingerprint = connection.execute(sa.text("SELECT id,fingerprint FROM builds WHERE source_url=:source_url AND fingerprint=:fingerprint"), {**builtin, "fingerprint": f"builtin:{builtin['build_id']}"}).fetchall()
        for row in same_fingerprint:
            remember(row.id)
            connection.execute(sa.text("UPDATE builds SET fingerprint=:fingerprint WHERE id=:id"), {"fingerprint": f"legacy:{row.fingerprint}:{row.id}", "id": row.id})
        same_version = connection.execute(sa.text("SELECT id FROM builds WHERE source_url=:source_url AND version=:version"), builtin).fetchall()
        for row in same_version:
            remember(row.id)
            next_version = connection.execute(sa.text("SELECT COALESCE(MAX(version),0)+1 FROM builds WHERE source_url=:source_url"), builtin).scalar_one()
            connection.execute(sa.text("UPDATE builds SET version=:version WHERE id=:id"), {"version": next_version, "id": row.id})
        connection.execute(builds.insert().values(**builtin, fingerprint=f"builtin:{builtin['build_id']}", created_at=now))
    pref = connection.execute(sa.text("SELECT value FROM app_preferences WHERE key='active_build_id'")).scalar()
    valid = connection.execute(sa.text("SELECT 1 FROM builds WHERE build_id=:id"), {"id": pref}).scalar() if pref else None
    target = pref if valid else "deadrabb1t-chaos-dot-lich-starter-v2"
    op.create_table("equipment_slots_new",
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("character_profiles.id"), primary_key=True),
        sa.Column("build_id", sa.String(120), sa.ForeignKey("builds.build_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("slot", sa.String(30), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=True),
    )
    connection.execute(sa.text("INSERT INTO equipment_slots_new(character_id,build_id,slot,item_id) SELECT character_id,:build_id,slot,item_id FROM equipment_slots"), {"build_id": target})
    op.drop_table("equipment_slots")
    op.rename_table("equipment_slots_new", "equipment_slots")


def downgrade() -> None:
    connection = op.get_bind()
    active = connection.execute(sa.text("SELECT value FROM app_preferences WHERE key='active_build_id'")).scalar()
    target = connection.execute(sa.text("SELECT build_id FROM equipment_slots WHERE build_id=:active LIMIT 1"), {"active": active}).scalar() if active else None
    target = target or connection.execute(sa.text("SELECT build_id FROM equipment_slots ORDER BY build_id LIMIT 1")).scalar()
    target = target or (connection.execute(sa.text("SELECT build_id FROM builds WHERE build_id=:active"), {"active": active}).scalar() if active else None)
    target = target or connection.execute(sa.text("SELECT build_id FROM builds ORDER BY CASE WHEN build_id='deadrabb1t-chaos-dot-lich-starter-v2' THEN 0 ELSE 1 END, build_id LIMIT 1")).scalar()
    op.create_table("equipment_slots_old",
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("character_profiles.id"), primary_key=True),
        sa.Column("slot", sa.String(30), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=True, unique=True),
    )
    if target:
        connection.execute(sa.text("INSERT INTO equipment_slots_old(character_id,slot,item_id) SELECT character_id,slot,item_id FROM equipment_slots WHERE build_id=:build_id"), {"build_id": target})
    op.drop_table("equipment_slots")
    op.rename_table("equipment_slots_old", "equipment_slots")
    connection.execute(sa.text("DELETE FROM builds WHERE fingerprint LIKE 'builtin:%'"))
    legacy_rows = connection.execute(sa.text("SELECT id,old_build_id,old_version,old_fingerprint FROM migration_0006_legacy_builds")).mappings().all()
    for row in legacy_rows:
        current = connection.execute(sa.text("SELECT build_id FROM builds WHERE id=:id"), row).scalar()
        if current:
            connection.execute(sa.text("UPDATE build_previews SET confirmed_build_id=:old WHERE confirmed_build_id=:current"), {"old": row["old_build_id"], "current": current})
            connection.execute(sa.text("UPDATE app_preferences SET value=:old WHERE key='active_build_id' AND value=:current"), {"old": row["old_build_id"], "current": current})
            connection.execute(sa.text("UPDATE builds SET build_id=:old_build_id,version=:old_version,fingerprint=:old_fingerprint WHERE id=:id"), row)
    preferred = connection.execute(sa.text("SELECT value FROM app_preferences WHERE key='active_build_id'")).scalar()
    remaining = connection.execute(sa.text("SELECT build_id FROM builds WHERE build_id=:id"), {"id": preferred}).scalar() if preferred else None
    remaining = remaining or connection.execute(sa.text("SELECT build_id FROM builds ORDER BY build_id LIMIT 1")).scalar()
    if remaining:
        connection.execute(sa.text("UPDATE app_preferences SET value=:value WHERE key='active_build_id'"), {"value": remaining})
    else:
        connection.execute(sa.text("DELETE FROM app_preferences WHERE key='active_build_id'"))
    op.drop_index("ix_builds_build_id", table_name="builds")
    op.create_index("ix_custom_builds_build_id", "builds", ["build_id"])
    op.rename_table("builds", "custom_builds")
    op.drop_table("migration_0006_legacy_builds")
