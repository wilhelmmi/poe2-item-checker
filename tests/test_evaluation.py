from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.api.routes as routes
from app.db.models import Base
from app.db.session import enable_sqlite_foreign_keys
from app.equipment.service import replace_equipment
from app.evaluation.openai_provider import OpenAIEvaluationProvider
from app.evaluation.provider import EvaluationProviderError
from app.evaluation.schemas import EvaluationInput, EvaluationResult
from app.main import app

ROOT = Path(__file__).parents[1]


def result() -> EvaluationResult:
    return EvaluationResult(
        recommendation="better", confidence="high", reasons=["Relevant."], warnings=[]
    )


@pytest.mark.parametrize(
    "claim",
    [
        "12 % mehr DPS.",
        "Der Score steigt.",
        "Marktwert: ein Divine.",
        "Das Item sollte gecraftet werden.",
    ],
)
def test_result_rejects_out_of_scope_claims(claim: str) -> None:
    with pytest.raises(ValidationError):
        EvaluationResult(recommendation="better", confidence="high", reasons=[claim], warnings=[])


def test_result_allows_essence_drain_reason() -> None:
    value = EvaluationResult(
        recommendation="better",
        confidence="high",
        reasons=["Essenzentzug profitiert von Chaos-Skill-Leveln."],
        warnings=[],
    )
    assert value.recommendation == "better"


class FakeProvider:
    name = "fake"
    model = "mock-model"

    def __init__(self) -> None:
        self.received: EvaluationInput | None = None

    async def evaluate(self, evaluation_input: EvaluationInput) -> EvaluationResult:
        self.received = evaluation_input
        return result()


class FailingProvider(FakeProvider):
    async def evaluate(self, evaluation_input: EvaluationInput) -> EvaluationResult:
        raise EvaluationProviderError("provider_refusal", "Sichere Ablehnung.")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'evaluation.db'}", connect_args={"check_same_thread": False}
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    async def override() -> AsyncIterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[routes.database] = override
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(routes.database, None)
        engine.dispose()


@pytest.mark.anyio
async def test_evaluate_sends_complete_comparison_context(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    with isolated_db() as db:
        replace_equipment(db, "wand", raw)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": raw, "target_slot": "wand"}
        )
    assert response.status_code == 200
    assert provider.received is not None
    assert provider.received.candidate.raw_text == raw
    assert provider.received.equipped and provider.received.equipped.raw_text == raw
    assert provider.received.target_slot == "wand"
    assert provider.received.observed_profile is not None
    assert provider.received.build.source_variant == "default-variant"
    assert response.json()["evaluation"]["recommendation"] == "better"
    assert "local_check" not in response.json() and "local_comparison" not in response.json()


@pytest.mark.anyio
async def test_provider_failure_has_no_local_recommendation(
    monkeypatch: pytest.MonkeyPatch,
    isolated_db: sessionmaker[Session],
) -> None:
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: FailingProvider())
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    with isolated_db() as db:
        replace_equipment(db, "wand", raw)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": raw, "target_slot": "wand"}
        )
    body = response.json()
    assert body["evaluation"] is None
    assert body["provider_status"] == "unavailable"
    assert "keine lokale empfehlung" in body["disclaimer"].lower()


@pytest.mark.anyio
async def test_openai_provider_uses_structured_comparison() -> None:
    from app.builds.registry import get_build, DEFAULT_BUILD_ID
    from app.parser.service import parse_with_warnings

    item = parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text()).item
    data = EvaluationInput(
        candidate=item,
        equipped=item,
        target_slot="wand",
        observed_profile=None,
        build=get_build(DEFAULT_BUILD_ID),
    )
    parse = pytest.importorskip("unittest.mock").AsyncMock(
        return_value=SimpleNamespace(output_parsed=result(), output=[], usage=None)
    )
    provider = OpenAIEvaluationProvider(
        api_key="x",
        model="mock",
        reasoning_effort="medium",
        timeout=1,
        max_retries=0,
        max_input_chars=50_000,
        max_output_tokens=100,
        rate_limit_per_minute=2,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )
    assert await provider.evaluate(data) == result()
    kwargs = parse.await_args.kwargs
    assert kwargs["text_format"] is EvaluationResult
    assert kwargs["store"] is False
    content = kwargs["input"][0]["content"]
    assert '"candidate"' in content and '"equipped"' in content and '"build"' in content
    assert '"raw_text"' not in content
    assert '"unknown_lines"' not in content
    assert '"notes"' not in content


@pytest.mark.anyio
async def test_provider_keeps_only_bounded_unknown_modifier_text() -> None:
    from app.builds.registry import get_build, DEFAULT_BUILD_ID
    from app.parser.service import parse_with_warnings

    item = parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text()).item
    unknown_modifier = item.modifiers[0].model_copy(
        update={
            "normalized_key": "unknown",
            "raw_text": "UNKNOWN_EFFECT_MARKER" + "x" * 600,
        }
    )
    unknown = item.model_copy(
        update={
            "modifiers": [unknown_modifier, *item.modifiers[1:]],
        }
    )
    data = EvaluationInput(
        candidate=unknown,
        equipped=item,
        target_slot="wand",
        observed_profile=None,
        build=get_build(DEFAULT_BUILD_ID),
    )
    parse = pytest.importorskip("unittest.mock").AsyncMock(
        return_value=SimpleNamespace(output_parsed=result(), output=[], usage=None)
    )
    provider = OpenAIEvaluationProvider(
        api_key="x",
        model="mock",
        reasoning_effort="medium",
        timeout=1,
        max_retries=0,
        max_input_chars=50_000,
        max_output_tokens=100,
        rate_limit_per_minute=2,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )
    await provider.evaluate(data)
    content = parse.await_args.kwargs["input"][0]["content"]
    assert "UNKNOWN_EFFECT_MARKER" in content
    assert "x" * 501 not in content
    assert content.count('"raw_text"') == 1


@pytest.mark.anyio
async def test_target_slot_and_build_are_required_and_valid() -> None:
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.post("/api/items/evaluate", json={"raw_text": raw})).status_code == 422
        response = await client.post(
            "/api/items/evaluate",
            json={"raw_text": raw, "target_slot": "wand", "build_id": "missing"},
        )
        builds = await client.get("/api/builds")
    assert response.status_code == 422
    assert builds.json()[0]["build_id"] == "deadrabb1t-chaos-dot-lich-starter-v1"


@pytest.mark.anyio
async def test_safe_collapsed_magic_is_formatted_before_provider(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    equipped = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    with isolated_db() as db:
        replace_equipment(db, "wand", equipped)
    collapsed = (
        "Item Class: Wands Rarity: Magic Apt Attuned Wand -------- Item Level: 66 "
        "-------- { Prefix Modifier — Caster } +2 to Level of all Chaos Spell Skills"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": collapsed, "target_slot": "wand"}
        )
    assert response.status_code == 200
    assert provider.received is not None
    assert "\n" in provider.received.candidate.raw_text
    assert provider.received.candidate.raw_text == response.json()["parse"]["item"]["raw_text"]


@pytest.mark.anyio
async def test_ambiguous_rare_never_calls_provider(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    equipped = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    with isolated_db() as db:
        replace_equipment(db, "wand", equipped)
    collapsed = equipped.replace("\n", " ")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": collapsed, "target_slot": "wand"}
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ambiguous_item_format"
    assert provider.received is None


@pytest.mark.anyio
async def test_equipped_item_is_required_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": raw, "target_slot": "wand"}
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "equipped_item_required"
    assert provider.received is None
