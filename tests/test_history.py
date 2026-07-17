import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import database, upload_backup
from app.core.config import get_settings
from app.db.models import Base, Evaluation
from app.db.session import enable_sqlite_foreign_keys
from app.main import app

ROOT = Path(__file__).parents[1]


@pytest.mark.anyio
async def test_streaming_restore_limit_without_content_length() -> None:
    chunks = iter((b"x" * 6_000_000, b"x" * 4_000_001))

    async def receive() -> dict:
        try:
            chunk = next(chunks)
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.request", "body": chunk, "more_body": True}

    request = Request({"type": "http", "method": "POST", "path": "/api/backup/restore",
                       "headers": []}, receive)
    with pytest.raises(HTTPException) as raised:
        await upload_backup(request, None)  # type: ignore[arg-type]
    assert raised.value.status_code == 413


def test_history_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "0003_explicit_empty_equipment")
    engine = create_engine(database_url)
    assert "snapshot" not in {column["name"] for column in inspect(engine).get_columns("evaluations")}
    command.upgrade(config, "head")
    upgraded = {column["name"] for column in inspect(engine).get_columns("evaluations")}
    assert {"status", "rule_version", "snapshot", "parent_evaluation_id", "updated_at"} <= upgraded
    assert any(index["name"] == "ux_sale_records_item_id" and index["unique"]
               for index in inspect(engine).get_indexes("sale_records"))
    command.downgrade(config, "0003_explicit_empty_equipment")
    downgraded = {column["name"] for column in inspect(engine).get_columns("evaluations")}
    assert "snapshot" not in downgraded
    engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def history_db(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'history.db'}", connect_args={"check_same_thread": False})
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
async def test_history_is_explicit_filterable_and_append_only(history_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    candidate = seed["equipment_raw_text"]["ring_1"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/equipment/import", json=seed)
        assert (await client.post("/api/items/evaluate", json={"raw_text": candidate, "target_slot": "ring_1"})).status_code == 200
        assert (await client.get("/api/history")).json()["total"] == 0
        saved = await client.post("/api/history", json={"raw_text": candidate, "target_slot": "ring_1"})
        assert saved.status_code == 201
        original = saved.json()
        assert original["snapshot"]["provider"] is None
        assert original["rule_version"] == 2
        assert (await client.get("/api/history", params={"slot": "wand"})).json()["total"] == 0
        assert (await client.get("/api/history", params={"slot": "ring_1", "rarity": "Rare"})).json()["total"] == 1
        updated = await client.put(f"/api/history/{original['id']}", json={
            "status": "listed", "listed_currency": "exalted", "listed_amount": "1.2500",
            "listed_at": "2026-07-16T12:00:00+00:00", "sold_at": None,
            "sold_currency": None, "sold_amount": None,
            "notes": "manual listing",
        })
        assert updated.status_code == 200
        assert updated.json()["sale"]["listed_amount"] == "1.2500"
        assert (await client.put(f"/api/history/{original['id']}", json={"status": "invalid"})).status_code == 422
        compared = await client.post(f"/api/history/{original['id']}/recompare")
        assert compared.status_code == 201
        assert compared.json()["id"] != original["id"]
        assert compared.json()["item_id"] == original["item_id"]
        assert compared.json()["status"] == "listed"
        assert compared.json()["sale"]["listed_amount"] == "1.2500"
        assert compared.json()["parent_evaluation_id"] == original["id"]
        synchronized = await client.put(f"/api/history/{compared.json()['id']}", json={
            "status": "stored", "listed_currency": "exalted", "listed_amount": "1.2500",
            "listed_at": "2026-07-16T12:00:00+00:00", "sold_at": None,
            "sold_currency": None, "sold_amount": None, "notes": "manual listing",
        })
        assert synchronized.status_code == 200
        parent = await client.get(f"/api/history/{original['id']}")
        assert parent.json()["status"] == "stored"
        assert parent.json()["sale"]["listed_amount"] == "1.2500"
        assert (await client.get("/api/history", params={"status": "stored"})).json()["total"] == 2
        assert (await client.get("/api/history", params={"status": "listed"})).json()["total"] == 0
        assert (await client.get("/api/history")).json()["total"] == 2
    with history_db() as db:
        assert db.get(Evaluation, original["id"]).status == "stored"


@pytest.mark.anyio
async def test_backup_roundtrip_and_invalid_restore_is_atomic(history_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/equipment/import", json=seed)
        await client.post("/api/history", json={
            "raw_text": seed["equipment_raw_text"]["boots"], "target_slot": "boots",
        })
        backup = (await client.get("/api/backup")).json()
        assert backup["schema_version"] == 1
        before = (await client.get("/api/history")).json()
        broken = {**backup, "evaluations": [{**backup["evaluations"][0], "item_id": "missing"}]}
        assert (await client.post("/api/backup/restore", json=broken)).status_code == 422
        assert (await client.get("/api/history")).json() == before
        profile = (await client.get("/api/profile")).json()
        await client.put("/api/profile", json={**profile, "notes": "changed"})
        restored = await client.post("/api/backup/restore", json=backup)
        assert restored.status_code == 204
        assert (await client.get("/api/profile")).json()["notes"] == backup["profile"]["notes"]
        assert (await client.get("/api/backup")).json() == backup


@pytest.mark.anyio
async def test_restore_rejects_duplicates_foreign_character_cycles_and_oversize(history_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/equipment/import", json=seed)
        await client.post("/api/history", json={
            "raw_text": seed["equipment_raw_text"]["boots"], "target_slot": "boots",
        })
        backup = (await client.get("/api/backup")).json()
        evaluation = backup["evaluations"][0]
        duplicates = {**backup, "evaluations": [evaluation, evaluation]}
        assert (await client.post("/api/backup/restore", json=duplicates)).status_code == 422
        foreign = {**backup, "evaluations": [{**evaluation, "character_id": 2}]}
        assert (await client.post("/api/backup/restore", json=foreign)).status_code == 422
        second = {**evaluation, "id": "00000000-0000-0000-0000-000000000002",
                  "parent_evaluation_id": evaluation["id"]}
        cycle_first = {**evaluation, "parent_evaluation_id": second["id"]}
        cyclic = {**backup, "evaluations": [cycle_first, second]}
        assert (await client.post("/api/backup/restore", json=cyclic)).status_code == 422
        oversized = await client.post("/api/backup/restore", content=b"{}", headers={
            "content-length": "10000001", "content-type": "application/json",
        })
        assert oversized.status_code == 413
        assert (await client.get("/api/history")).json()["total"] == 1


@pytest.mark.anyio
async def test_sale_metadata_validation(history_db) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        saved = (await client.post("/api/history", json={
            "raw_text": seed["equipment_raw_text"]["boots"], "target_slot": "boots",
        })).json()
        endpoint = f"/api/history/{saved['id']}"
        assert (await client.put(endpoint, json={"status": "listed"})).status_code == 422
        assert (await client.put(endpoint, json={
            "status": "listed", "listed_amount": "1", "listed_currency": "exalted",
        })).status_code == 422
        assert (await client.put(endpoint, json={
            "status": "sold", "listed_at": "2026-07-17T00:00:00Z", "listed_amount": "1",
            "listed_currency": "exalted", "sold_at": "2026-07-16T00:00:00Z",
            "sold_amount": "2", "sold_currency": "exalted",
        })).status_code == 422
