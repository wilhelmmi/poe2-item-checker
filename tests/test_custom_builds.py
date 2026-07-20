from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.builds.provider import extract_citations
from app.builds.schemas import BuildAnalysis
from app.builds.service import (canonicalize_source_url, confirm_preview, create_preview,
                                get_active, get_any_build, list_all_builds, set_active)
from app.db.models import Base, BuildPreview, CustomBuild


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
    with Session(engine) as db:
        preview = create_preview(db, "https://guide.example.com/build", analysis(), [], "openai", "test")
        first = confirm_preview(db, preview.id)
        second = confirm_preview(db, preview.id)
        assert first.build_id == second.build_id
        assert first.build_id.startswith("custom-")
        assert db.query(CustomBuild).count() == 1
        assert get_any_build(db, first.build_id).name == "Chaos Lich"
        assert first.build_id in {build.build_id for build in list_all_builds(db)}
        assert set_active(db, first.build_id) == first.build_id
        assert get_active(db) == first.build_id


def test_changed_analysis_creates_next_version_for_same_url() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = confirm_preview(db, create_preview(db, "https://guide.example.com/build",
            analysis(), [], "openai", "test").id)
        second = confirm_preview(db, create_preview(db, "https://guide.example.com/build",
            analysis("Chaos Lich Updated"), [], "openai", "test").id)
        assert (first.version, second.version) == (1, 2)


def test_expired_preview_cannot_be_promoted() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        preview = create_preview(db, "https://guide.example.com/build", analysis(), [], "openai", "test")
        preview.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        with pytest.raises(ValueError, match="preview_expired"):
            confirm_preview(db, preview.id)
        assert db.query(BuildPreview).count() == 1
        assert db.query(CustomBuild).count() == 0
