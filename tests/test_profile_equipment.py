import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import database
from app.db.models import Base, EquipmentSlot, Item
from app.db.session import enable_sqlite_foreign_keys
from app.main import app

ROOT = Path(__file__).parents[1]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def isolated_db(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'management.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    async def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[database] = override
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.anyio
async def test_profile_singleton_strict_crud(isolated_db) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get("/api/profile")
        assert initial.status_code == 200
        body = initial.json()
        body.update({"character_level": 70, "strength": 50, "spirit": 120, "spirit_reserved": 100})
        updated = await client.put("/api/profile", json=body)
        assert updated.status_code == 200
        assert (await client.get("/api/profile")).json()["character_level"] == 70
        assert (await client.put("/api/profile", json={**body, "unknown": 1})).status_code == 422


@pytest.mark.anyio
async def test_equipment_replace_keeps_old_item_and_separates_rings(isolated_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.put("/api/equipment/ring_1", json={"raw_text": seed["equipment_raw_text"]["ring_1"]})
        assert first.status_code == 200
        old_id = first.json()["id"]
        second = await client.put("/api/equipment/ring_1", json={"raw_text": seed["equipment_raw_text"]["ring_2"]})
        assert second.status_code == 200
        assert (await client.put("/api/equipment/wand", json={"raw_text": seed["equipment_raw_text"]["ring_1"]})).status_code == 422
        await client.put("/api/equipment/ring_2", json={"raw_text": seed["equipment_raw_text"]["ring_1"]})
        equipment = (await client.get("/api/equipment")).json()["slots"]
        assert set(equipment) == {"wand", "focus", "helmet", "body_armour", "gloves", "boots", "belt", "ring_1", "ring_2", "amulet"}
        assert equipment["ring_1"]["id"] != equipment["ring_2"]["id"]
    with isolated_db() as db:
        assert db.get(Item, old_id) is not None


@pytest.mark.anyio
async def test_seed_import_export_roundtrip_and_atomic_failure(isolated_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        imported = await client.post("/api/equipment/import", json=seed)
        assert imported.status_code == 200
        assert sum(value is not None for value in imported.json()["slots"].values()) == 10
        exported = (await client.get("/api/equipment/export")).json()
        assert exported["schema_version"] == 2
        assert exported["equipment_raw_text"] == seed["equipment_raw_text"]
        exported["profile"].update({"character_level": 77, "spirit_required": 120, "notes": "roundtrip"})
        exported["equipment_raw_text"]["focus"] = None
        assert (await client.post("/api/equipment/import", json=exported)).status_code == 200
        assert (await client.get("/api/equipment")).json()["slots"]["focus"] is None
        assert (await client.get("/api/profile")).json()["notes"] == "roundtrip"
        partial_v2 = {**exported, "equipment_raw_text": {"wand": None}}
        rejected = await client.post("/api/equipment/import", json=partial_v2)
        assert rejected.status_code == 422
        assert (await client.get("/api/equipment/export")).json()["equipment_raw_text"] == exported["equipment_raw_text"]
        broken = {**seed, "equipment_raw_text": {**seed["equipment_raw_text"], "wand": "bad"}}
        assert (await client.post("/api/equipment/import", json=broken)).status_code == 422
        assert (await client.get("/api/equipment/export")).json()["equipment_raw_text"]["focus"] is None


@pytest.mark.anyio
async def test_evaluate_hard_checks_are_server_owned(isolated_db, monkeypatch) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/equipment/import", json=seed)
        profile = (await client.get("/api/profile")).json()
        profile.update({"character_level": 70, "intelligence": 100, "fire_resistance": 75,
                        "cold_resistance": 75, "lightning_resistance": 75,
                        "chaos_resistance": 75, "spirit": 100, "spirit_required": 100})
        await client.put("/api/profile", json=profile)
        candidate = "Item Class: Boots\nRarity: Magic\nPlain Boots\n--------\nRequires: Level 60, 120 Int\n--------\nItem Level: 66\n--------\n{ Prefix Modifier — Speed }\n10% increased Movement Speed"
        response = await client.post("/api/items/evaluate", json={"raw_text": candidate, "target_slot": "boots"})
        assert response.status_code == 200
        checks = {check["code"]: check for check in response.json()["hard_checks"]["checks"]}
        assert checks["requirement_intelligence"]["status"] == "fail"
        assert checks["boots_movement_speed_loss"]["status"] == "pass"
        strong_loss = candidate.replace("10% increased Movement Speed", "5% increased Movement Speed")
        strong = await client.post("/api/items/evaluate", json={"raw_text": strong_loss, "target_slot": "boots"})
        strong_checks = {check["code"]: check for check in strong.json()["hard_checks"]["checks"]}
        assert strong_checks["boots_movement_speed_loss"]["status"] == "fail"
        assert response.json()["evaluation"] is None  # no configured provider still preserves checks
        assert response.json()["local_comparison"]["comparisons"][0]["candidate"]["score"] >= 0
        mismatch = await client.post("/api/items/evaluate", json={"raw_text": candidate, "target_slot": "wand"})
        assert mismatch.status_code == 422
        assert mismatch.json()["detail"]["code"] == "item_slot_mismatch"
        ring = await client.post("/api/items/evaluate", json={
            "raw_text": seed["equipment_raw_text"]["ring_1"], "target_slot": "ring_2",
        })
        assert ring.status_code == 200
        both_rings = await client.post("/api/items/evaluate", json={
            "raw_text": seed["equipment_raw_text"]["ring_1"],
        })
        assert [value["target_slot"] for value in both_rings.json()["local_comparison"]["comparisons"]] == ["ring_1", "ring_2"]
        assert len(ring.json()["local_comparison"]["comparisons"]) == 1
        no_target = await client.post("/api/items/evaluate", json={"raw_text": candidate})
        no_target_checks = {check["code"]: check for check in no_target.json()["hard_checks"]["checks"]}
        assert no_target_checks["requirement_intelligence"]["status"] == "fail"
        assert no_target.json()["local_comparison"]["comparisons"][0]["target_slot"] == "boots"
        with isolated_db() as db:
            db.delete(db.get(EquipmentSlot, (1, "boots")))
            db.commit()
        missing = await client.post("/api/items/evaluate", json={"raw_text": candidate, "target_slot": "boots"})
        missing_checks = {check["code"]: check for check in missing.json()["hard_checks"]["checks"]}
        assert missing_checks["requirement_intelligence"]["status"] == "unknown"
        assert missing_checks["boots_movement_speed_loss"]["status"] == "unknown"
        with isolated_db() as db:
            db.add(EquipmentSlot(character_id=1, slot="boots", item_id=None))
            db.commit()
        empty = await client.post("/api/items/evaluate", json={"raw_text": candidate, "target_slot": "boots"})
        empty_checks = {check["code"]: check for check in empty.json()["hard_checks"]["checks"]}
        assert empty_checks["requirement_intelligence"]["status"] == "fail"
        assert empty_checks["boots_movement_speed_loss"]["status"] == "pass"
