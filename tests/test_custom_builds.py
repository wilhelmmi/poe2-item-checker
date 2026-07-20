from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from types import SimpleNamespace

import pytest
import httpx
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes import database
import app.builds.service as build_service
from app.builds.registry import DEFAULT_BUILD_ID, V1_BUILD_ID
from app.builds.provider import extract_citations
from app.builds.schemas import BuildAnalysis
from app.builds.service import (canonicalize_source_url, confirm_preview, create_preview,
                                delete_custom_build, get_active, get_any_build, list_all_builds,
                                set_active)
from app.db.models import AppPreference, Base, BuildPreview, CustomBuild
from app.db.session import enable_sqlite_foreign_keys
from app.main import app
from tests.build_seed import seed_builtin_builds


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def analysis(name: str = "Chaos Lich") -> BuildAnalysis:
    return BuildAnalysis(name=name, author="Guide Author", source_variant="Endgame",
        archetype="Chaos damage over time", core_skills=["Essence Drain"],
        offensive_priorities=["Chaos skill levels"], defensive_priorities=["Energy Shield"],
        item_priorities=["+ Level to Chaos Spell Skills"], low_value_stats=["Accuracy"],
        constraints=["Mana sustain"], uncertainties=["Exact breakpoint unknown"])


@pytest.mark.parametrize("url", [
    "http://localhost/build", "http://127.0.0.1/build", "http://[::1]/build",
    "http://10.0.0.1/build", "https://user:secret@example.com/build",
    "https://example.local/build", "file:///etc/passwd", "https://example.com/build#fragment",
    "https://example.com/\nattack",
])
def test_build_url_rejects_ssrf_and_ambiguous_targets(url: str) -> None:
    with pytest.raises(ValueError, match="invalid_build_url"):
        canonicalize_source_url(url)


def test_build_url_canonicalizes_public_hostname() -> None:
    assert canonicalize_source_url(" HTTPS://Guides.Example.COM/path?q=1 ") == \
        "https://guides.example.com/path?q=1"


def test_citations_only_come_from_url_citation_annotations() -> None:
    annotations = [
        SimpleNamespace(type="url_citation", url="https://guide.example.com/build", title="Guide"),
        SimpleNamespace(type="other", url="https://evil.example/", title="Ignored"),
        SimpleNamespace(type="url_citation", url="javascript:alert(1)", title="Invalid"),
    ]
    response = SimpleNamespace(output=[SimpleNamespace(content=[SimpleNamespace(annotations=annotations)])])
    assert [str(item.url) for item in extract_citations(response)] == ["https://guide.example.com/build"]


def test_preview_confirmation_is_persistent_idempotent_and_activatable() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as seed_db:
        seed_builtin_builds(seed_db)
    with Session(engine) as db:
        preview = create_preview(db, "https://guide.example.com/build", analysis(), [], "openai", "test")
        first = confirm_preview(db, preview.id)
        second = confirm_preview(db, preview.id)
        assert first.build_id == second.build_id
        assert first.build_id.startswith("custom-")
        assert db.query(CustomBuild).count() == 3
        assert get_any_build(db, first.build_id).name == "Chaos Lich"
        assert first.build_id in {build.build_id for build in list_all_builds(db)}
        assert set_active(db, first.build_id) == first.build_id
        assert get_active(db) == first.build_id


def test_changed_analysis_creates_next_version_for_same_url() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as seed_db:
        seed_builtin_builds(seed_db)
    with Session(engine) as db:
        first = confirm_preview(db, create_preview(db, "https://guide.example.com/build",
            analysis(), [], "openai", "test").id)
        second = confirm_preview(db, create_preview(db, "https://guide.example.com/build",
            analysis("Chaos Lich Updated"), [], "openai", "test").id)
        assert (first.version, second.version) == (1, 2)


def test_delete_custom_build_clears_previews_and_resets_active_build() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as seed_db:
        seed_builtin_builds(seed_db)
    with Session(engine) as db:
        preview = create_preview(db, "https://guide.example.com/build", analysis(), [], "openai", "test")
        custom = confirm_preview(db, preview.id)
        set_active(db, custom.build_id)
        assert delete_custom_build(db, custom.build_id) == V1_BUILD_ID
        assert db.get(CustomBuild, custom.id) is None
        assert db.get(BuildPreview, preview.id).confirmed_build_id is None
        assert db.get(AppPreference, "active_build_id").value == V1_BUILD_ID


def test_delete_accepts_builtin_and_rejects_unknown_builds() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as seed_db:
        seed_builtin_builds(seed_db)
    with Session(engine) as db:
        assert delete_custom_build(db, DEFAULT_BUILD_ID) == V1_BUILD_ID
        with pytest.raises(ValueError, match="unknown_build"):
            delete_custom_build(db, "custom-missing-v1")


def test_deleting_every_build_leaves_nullable_active_and_confirm_recovers() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_builtin_builds(db)
        assert delete_custom_build(db, DEFAULT_BUILD_ID) == V1_BUILD_ID
        assert delete_custom_build(db, V1_BUILD_ID) is None
        assert get_active(db) is None
        preview = create_preview(db, "https://guide.example.com/empty", analysis(), [], "openai", "test")
        created = confirm_preview(db, preview.id)
        assert get_active(db) == created.build_id


def test_concurrent_activate_then_delete_cannot_leave_deleted_build_active(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent-build.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as seed_db:
        seed_builtin_builds(seed_db)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        custom_id = confirm_preview(db, create_preview(db, "https://guide.example.com/build", analysis(), [], "openai", "test").id).build_id

    validation_started = Event()
    allow_activation_commit = Event()
    deletion_finished = Event()
    errors: list[BaseException] = []
    original_get_any_build = build_service.get_any_build

    def blocking_get_any_build(db: Session, build_id: str):
        result = original_get_any_build(db, build_id)
        if build_id == custom_id and not validation_started.is_set():
            validation_started.set()
            assert allow_activation_commit.wait(2)
        return result

    monkeypatch.setattr(build_service, "get_any_build", blocking_get_any_build)

    def activate() -> None:
        try:
            with factory() as db:
                set_active(db, custom_id)
        except BaseException as exc:
            errors.append(exc)

    def remove() -> None:
        try:
            with factory() as db:
                assert delete_custom_build(db, custom_id) == V1_BUILD_ID
        except BaseException as exc:
            errors.append(exc)
        finally:
            deletion_finished.set()

    activating = Thread(target=activate)
    deleting = Thread(target=remove)
    activating.start()
    assert validation_started.wait(2)
    deleting.start()
    assert not deletion_finished.wait(0.1)
    allow_activation_commit.set()
    activating.join(2)
    deleting.join(2)
    assert not errors
    assert not activating.is_alive() and not deleting.is_alive()
    with factory() as db:
        assert get_active(db) == V1_BUILD_ID
        assert db.scalar(select(CustomBuild).where(CustomBuild.build_id == custom_id)) is None
        assert db.get(AppPreference, "active_build_id").value == V1_BUILD_ID
    engine.dispose()


def test_confirmation_and_deletion_share_the_build_mutation_lock(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'confirm-delete.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        seed_builtin_builds(db)
        preview_id = create_preview(db, "https://guide.example.com/race", analysis(), [], "openai", "test").id
    entered = Event()
    release = Event()
    deleted = Event()
    original = build_service._confirm_preview

    def blocking_confirm(db: Session, preview_id: str):
        entered.set()
        assert release.wait(2)
        return original(db, preview_id)

    monkeypatch.setattr(build_service, "_confirm_preview", blocking_confirm)
    confirmed: list[str] = []

    def confirm() -> None:
        with factory() as db:
            confirmed.append(confirm_preview(db, preview_id).build_id)

    def remove() -> None:
        with factory() as db:
            delete_custom_build(db, DEFAULT_BUILD_ID)
        deleted.set()

    confirming = Thread(target=confirm)
    removing = Thread(target=remove)
    confirming.start()
    assert entered.wait(2)
    removing.start()
    assert not deleted.wait(0.1)
    release.set()
    confirming.join(2)
    removing.join(2)
    assert confirmed and deleted.is_set()
    engine.dispose()


@pytest.mark.anyio
async def test_delete_build_api_returns_status_codes_and_new_active(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'build-delete.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    with Session(engine) as seed_db:
        seed_builtin_builds(seed_db)
    factory = sessionmaker(engine, expire_on_commit=False)
    async def override():
        with factory() as session:
            yield session
    app.dependency_overrides[database] = override
    try:
        with factory() as db:
            custom = confirm_preview(db, create_preview(db, "https://guide.example.com/build", analysis(), [], "openai", "test").id)
            set_active(db, custom.build_id)
            custom_id = custom.build_id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            builtin = await client.delete(f"/api/builds/{DEFAULT_BUILD_ID}")
            missing = await client.delete("/api/builds/custom-missing-v1")
            deleted = await client.delete(f"/api/builds/{custom_id}")
        assert builtin.status_code == 200
        assert missing.status_code == 404
        assert deleted.json() == {"deleted_build_id": custom_id, "active_build_id": V1_BUILD_ID}
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_expired_preview_cannot_be_promoted() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as seed_db:
        seed_builtin_builds(seed_db)
    with Session(engine) as db:
        preview = create_preview(db, "https://guide.example.com/build", analysis(), [], "openai", "test")
        preview.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(ValueError, match="preview_expired"):
            confirm_preview(db, preview.id)
        assert db.query(BuildPreview).count() == 1
        assert db.query(CustomBuild).count() == 2
