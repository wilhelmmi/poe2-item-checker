import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.api.routes as routes
from app.api.routes import database
from app.builds.registry import DEFAULT_BUILD_ID
from app.db.models import Base, Item
from app.db.session import enable_sqlite_foreign_keys
from app.equipment.service import parse_equipment
from app.evaluation.provider import EvaluationProviderError
from app.main import app
from tests.build_seed import seed_builtin_builds

ROOT = Path(__file__).parents[1]
STAFF = (
    "Item Class: Staves\nRarity: Magic\nVorpal Ashen Staff of Siphoning\n--------\n"
    "Requires: Level 44\n--------\nItem Level: 66\n--------\n"
    "Grants Skill: Level 14 Firebolt\n--------\n"
    '{ Prefix Modifier "Vorpal" (Tier: 3) — Damage, Elemental, Lightning }\n'
    "Gain 44(43-48)% of Damage as Extra Lightning Damage\n"
    '{ Suffix Modifier "of Siphoning" (Tier: 3) — Mana }\n'
    "Gain 23(21-27) Mana per enemy killed"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def isolated_db(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'management.db'}", connect_args={"check_same_thread": False}
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        seed_builtin_builds(db)

    async def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[database] = override
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.anyio
async def test_profile_singleton_strict_crud(isolated_db) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
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
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.put(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/ring_1", json={"raw_text": seed["equipment_raw_text"]["ring_1"]}
        )
        assert first.status_code == 200
        old_id = first.json()["id"]
        second = await client.put(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/ring_1", json={"raw_text": seed["equipment_raw_text"]["ring_2"]}
        )
        assert second.status_code == 200
        assert (
            await client.put(
                f"/api/builds/{DEFAULT_BUILD_ID}/equipment/wand", json={"raw_text": seed["equipment_raw_text"]["ring_1"]}
            )
        ).status_code == 422
        await client.put(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/ring_2", json={"raw_text": seed["equipment_raw_text"]["ring_1"]}
        )
        equipment = (await client.get(f"/api/builds/{DEFAULT_BUILD_ID}/equipment")).json()["slots"]
        assert set(equipment) == {
            "wand",
            "focus",
            "helmet",
            "body_armour",
            "gloves",
            "boots",
            "belt",
            "ring_1",
            "ring_2",
            "amulet",
        }
        assert equipment["ring_1"]["id"] != equipment["ring_2"]["id"]
    with isolated_db() as db:
        assert db.get(Item, old_id) is not None


@pytest.mark.anyio
async def test_equipment_is_isolated_between_builds(isolated_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    other_build = "deadrabb1t-chaos-dot-lich-starter-v1"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        saved = await client.put(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/wand",
            json={"raw_text": seed["equipment_raw_text"]["wand"]},
        )
        assert saved.status_code == 200
        primary = await client.get(f"/api/builds/{DEFAULT_BUILD_ID}/equipment")
        secondary = await client.get(f"/api/builds/{other_build}/equipment")
    assert primary.json()["slots"]["wand"] is not None
    assert secondary.json()["slots"]["wand"] is None


@pytest.mark.anyio
async def test_staff_loadout_is_atomic_and_focus_removes_staff(isolated_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.put(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/wand", json={"raw_text": seed["equipment_raw_text"]["wand"]})
        await client.put(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/focus", json={"raw_text": seed["equipment_raw_text"]["focus"]})
        equipped = await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/equip", json={"raw_text": STAFF})
        assert equipped.status_code == 200, equipped.text
        assert equipped.json()["slots"]["wand"]["item"]["item_class"] == "Staves"
        assert equipped.json()["slots"]["focus"] is None

        focus = await client.put(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/focus", json={"raw_text": seed["equipment_raw_text"]["focus"]}
        )
        assert focus.status_code == 200
        slots = (await client.get(f"/api/builds/{DEFAULT_BUILD_ID}/equipment")).json()["slots"]
        assert slots["wand"] is None
        assert slots["focus"]["item"]["item_class"] == "Foci"


@pytest.mark.anyio
async def test_staff_export_and_import_use_wand_with_empty_focus(isolated_db) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/equip", json={"raw_text": STAFF})
        exported = (await client.get(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/export")).json()
        assert exported["equipment_raw_text"]["wand"] == STAFF
        assert exported["equipment_raw_text"]["focus"] is None
        assert (await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=exported)).status_code == 200
        conflicting = {
            **exported,
            "equipment_raw_text": {
                **exported["equipment_raw_text"],
                "focus": json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())["equipment_raw_text"]["focus"],
            },
        }
        response = await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=conflicting)
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "two_handed_slot_conflict"


@pytest.mark.anyio
async def test_partial_v1_imports_preserve_two_handed_invariant_both_directions(
    isolated_db,
) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())

    def partial(slot: str, raw_text: str) -> dict:
        return {
            "schema_version": 1,
            "profile": seed["profile"],
            "equipment_raw_text": {slot: raw_text},
        }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.put(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/focus", json={"raw_text": seed["equipment_raw_text"]["focus"]}
        )
        staff_import = await client.post(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=partial("wand", STAFF)
        )
        assert staff_import.status_code == 200, staff_import.text
        assert staff_import.json()["slots"]["wand"]["item"]["item_class"] == "Staves"
        assert staff_import.json()["slots"]["focus"] is None

        focus_import = await client.post(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import",
            json=partial("focus", seed["equipment_raw_text"]["focus"]),
        )
        assert focus_import.status_code == 200, focus_import.text
        assert focus_import.json()["slots"]["wand"] is None
        assert focus_import.json()["slots"]["focus"]["item"]["item_class"] == "Foci"


@pytest.mark.anyio
async def test_seed_import_export_roundtrip_and_atomic_failure(isolated_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        imported = await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=seed)
        assert imported.status_code == 200
        assert sum(value is not None for value in imported.json()["slots"].values()) == 10
        exported = (await client.get(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/export")).json()
        assert exported["schema_version"] == 2
        assert exported["equipment_raw_text"] == seed["equipment_raw_text"]
        exported["profile"].update(
            {"character_level": 77, "spirit_required": 120, "notes": "roundtrip"}
        )
        exported["equipment_raw_text"]["focus"] = None
        assert (await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=exported)).status_code == 200
        assert (await client.get(f"/api/builds/{DEFAULT_BUILD_ID}/equipment")).json()["slots"]["focus"] is None
        assert (await client.get("/api/profile")).json()["notes"] == "roundtrip"
        partial_v2 = {**exported, "equipment_raw_text": {"wand": None}}
        rejected = await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=partial_v2)
        assert rejected.status_code == 422
        assert rejected.json() == {
            "detail": {
                "code": "invalid_equipment_snapshot",
                "message": (
                    "Der Equipment-Snapshot ist unvollständig oder entspricht nicht dem "
                    "unterstützten Schema."
                ),
            }
        }
        assert seed["equipment_raw_text"]["wand"] not in rejected.text
        assert (await client.get(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/export")).json()["equipment_raw_text"] == exported[
            "equipment_raw_text"
        ]
        broken = {**seed, "equipment_raw_text": {**seed["equipment_raw_text"], "wand": "bad"}}
        assert (await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=broken)).status_code == 422
        assert (await client.get(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/export")).json()["equipment_raw_text"][
            "focus"
        ] is None


@pytest.mark.anyio
async def test_structured_docs_import_populates_equipment_used_by_evaluate(
    isolated_db, monkeypatch
) -> None:
    def unavailable_provider():
        raise EvaluationProviderError("provider_not_configured", "Nicht konfiguriert.")

    monkeypatch.setattr(routes, "get_evaluation_provider", unavailable_provider)
    snapshot = json.loads((ROOT / "tests/fixtures/structured_equipment.json").read_text())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        imported = await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=snapshot)
        assert imported.status_code == 200, imported.text
        slots = imported.json()["slots"]
        assert all(slots[slot] is not None for slot in slots)
        assert slots["ring_1"]["item"]["name"] == "Skull Knot"
        assert slots["ring_2"]["item"]["name"] == "Pandemonium Nail"
        for source_slot, stored_slot in {
            "wand": "wand",
            "focus": "focus",
            "helmet": "helmet",
            "body_armour": "body_armour",
            "gloves": "gloves",
            "boots": "boots",
            "belt": "belt",
            "ring1": "ring_1",
            "ring2": "ring_2",
            "amulet": "amulet",
        }.items():
            assert len(slots[stored_slot]["item"]["modifiers"]) == len(
                snapshot[source_slot]["mods"]
            )

        candidate = (
            "Item Class: Wands\nRarity: Magic\nApt Attuned Wand\n--------\n"
            "Item Level: 66\n--------\n+2 to Level of all Chaos Spell Skills"
        )
        evaluated = await client.post(
            "/api/items/evaluate",
            json={
                "raw_text": candidate,
                "target_slot": "wand",
                    "build_id": DEFAULT_BUILD_ID,
            },
        )
        assert evaluated.status_code == 200, evaluated.text
        assert evaluated.json()["equipped"]["name"] == "Bramble Needle"


@pytest.mark.anyio
async def test_structured_import_rejects_unknown_item_fields(isolated_db) -> None:
    snapshot = json.loads((ROOT / "tests/fixtures/structured_equipment.json").read_text())
    snapshot["wand"]["unmapped_stat"] = 42
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=snapshot)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_equipment_snapshot"


@pytest.mark.anyio
async def test_evaluate_flow_has_no_local_hard_checks(isolated_db, monkeypatch) -> None:
    def unavailable_provider():
        raise EvaluationProviderError("provider_not_configured", "Nicht konfiguriert.")

    monkeypatch.setattr(routes, "get_evaluation_provider", unavailable_provider)
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/import", json=seed)
        profile = (await client.get("/api/profile")).json()
        profile.update(
            {
                "character_level": 70,
                "intelligence": 100,
                "fire_resistance": 75,
                "cold_resistance": 75,
                "lightning_resistance": 75,
                "chaos_resistance": 75,
                "spirit": 100,
                "spirit_required": 100,
            }
        )
        await client.put("/api/profile", json=profile)
        candidate = "Item Class: Boots\nRarity: Magic\nPlain Boots\n--------\nRequires: Level 60, 120 Int\n--------\nItem Level: 66\n--------\n{ Prefix Modifier — Speed }\n10% increased Movement Speed"
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": candidate, "target_slot": "boots"}
        )
        assert response.status_code == 200
        body = response.json()
        assert "hard_checks" not in body
        assert "local_comparison" not in body
        assert body["evaluation"] is None
        mismatch = await client.post(
            "/api/items/evaluate", json={"raw_text": candidate, "target_slot": "wand"}
        )
        assert mismatch.status_code == 422
        assert mismatch.json()["detail"]["code"] == "item_slot_mismatch"
        no_target = await client.post("/api/items/evaluate", json={"raw_text": candidate})
        assert no_target.status_code == 422


@pytest.mark.anyio
async def test_equipment_save_autoformats_only_safe_collapsed_input(isolated_db) -> None:
    safe = (
        "Item Class: Wands Rarity: Magic Apt Attuned Wand -------- Item Level: 66 "
        "-------- { Prefix Modifier — Caster } +2 to Level of all Chaos Spell Skills"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        saved = await client.put(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/wand", json={"raw_text": safe})
        assert saved.status_code == 200
        assert "\n" in saved.json()["item"]["raw_text"]
        rare = safe.replace("Rarity: Magic", "Rarity: Rare").replace("Apt Attuned", "Doom")
        rejected = await client.put(f"/api/builds/{DEFAULT_BUILD_ID}/equipment/wand", json={"raw_text": rare})
        assert rejected.status_code == 422
        assert rejected.json()["detail"]["code"] == "ambiguous_item_format"


def test_bulk_import_parser_never_silently_autoformats_collapsed_input() -> None:
    collapsed = (
        "Item Class: Wands Rarity: Magic Apt Attuned Wand -------- Item Level: 66 "
        "-------- { Prefix Modifier — Caster } +2 to Level of all Chaos Spell Skills"
    )
    with pytest.raises(ValueError, match="incomplete_item"):
        parse_equipment(collapsed)
