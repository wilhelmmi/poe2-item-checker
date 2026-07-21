import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
DEFAULT_BUILD_ID = "deadrabb1t-chaos-dot-lich-starter-v2"
SOURCE = "https://mobalytics.gg/poe-2/builds/chaos-dot-lich-starter-deadrabbit?ws-ngf5-f7d82102-7e77-4a44-ad24-33b67e8ae7bf=activeVariantId%2Cdefault-variant"


def migrate(database: Path, revision: str) -> None:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database}"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade" if revision != "0005-down" else "downgrade", "0005" if revision == "0005-down" else revision], cwd=ROOT, env=env, check=True, capture_output=True, text=True)


def insert_legacy_build(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO custom_builds VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("legacy-id", "deadrabb1t-chaos-dot-lich-starter-v1", 1, "Legacy", "A", SOURCE,
         "legacy-fp", "legacy", "legacy", "[]", "[]", "[]", "[]", "[]", "[]", "[]", "2020-01-01"),
    )


def test_0006_fresh_upgrade(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    migrate(database, "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM builds").fetchone()[0] == 2


@pytest.mark.parametrize("active", [None, "missing"])
def test_0006_assigns_legacy_equipment_to_default_for_missing_or_invalid_active(tmp_path: Path, active: str | None) -> None:
    database = tmp_path / f"active-{active}.db"
    migrate(database, "0005")
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO character_profiles(id,name,build_stage,resistance_cap,notes) VALUES(1,'x','x',75,'')")
        connection.execute("INSERT INTO items(id,raw_text,unknown_lines,sockets,armour_augmented,evasion_augmented,energy_shield_augmented,identified,corrupted,created_at) VALUES('item','x','[]','[]',0,0,0,1,0,CURRENT_TIMESTAMP)")
        connection.execute("INSERT INTO equipment_slots(character_id,slot,item_id) VALUES(1,'wand','item')")
        if active is not None:
            connection.execute("INSERT INTO app_preferences VALUES('active_build_id',?)", (active,))
        connection.commit()
    migrate(database, "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT build_id FROM equipment_slots").fetchone()[0] == DEFAULT_BUILD_ID


def test_0006_collision_roundtrip_preserves_legacy_build(tmp_path: Path) -> None:
    database = tmp_path / "collision.db"
    migrate(database, "0005")
    with sqlite3.connect(database) as connection:
        insert_legacy_build(connection)
        connection.execute("INSERT INTO app_preferences VALUES('active_build_id','deadrabb1t-chaos-dot-lich-starter-v1')")
        connection.commit()
    migrate(database, "head")
    with sqlite3.connect(database) as connection:
        rows = connection.execute("SELECT build_id,version FROM builds ORDER BY build_id").fetchall()
        assert len(rows) == 3
        assert any(build_id.endswith("-legacy-legacy-id") and version == 3 for build_id, version in rows)
    migrate(database, "0005-down")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT build_id,version,fingerprint FROM custom_builds").fetchone() == (
            "deadrabb1t-chaos-dot-lich-starter-v1", 1, "legacy-fp",
        )
        assert connection.execute("SELECT value FROM app_preferences WHERE key='active_build_id'").fetchone()[0] == "deadrabb1t-chaos-dot-lich-starter-v1"
