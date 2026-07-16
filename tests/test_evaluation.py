import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.api.routes as routes
from app.core.config import Settings, get_settings
from app.db.models import Base
from app.db.session import enable_sqlite_foreign_keys
from app.evaluation.openai_provider import OpenAIEvaluationProvider
from app.evaluation.provider import EvaluationProviderError
from app.evaluation.schemas import EvaluationResult
from app.evaluation.service import get_evaluation_provider
from app.facts.engine import check_item_facts
from app.main import app
from app.parser.service import parse_with_warnings

ROOT = Path(__file__).parents[1]


def result() -> EvaluationResult:
    return EvaluationResult.model_validate({
        "build": {"suitability": "unknown_without_profile", "reasons": ["Kein Profil."], "warnings": []},
        "trade": {"recommendation": "manual_review", "reasons": ["Keine Live-Daten."], "warnings": []},
        "crafting": {"recommendation": "needs_review", "reasons": ["Basis prüfen."], "warnings": []},
        "confidence": "low", "confidence_reasons": ["Equipment fehlt."], "warnings": [],
    })


class FakeProvider:
    name = "fake"
    model = "mock-model"

    async def evaluate(self, facts):
        assert facts.name
        return result()


class FailingProvider(FakeProvider):
    async def evaluate(self, facts):
        raise EvaluationProviderError("provider_refusal", "Sichere Ablehnung.")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> Iterator[None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'evaluation.db'}",
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    async def override() -> AsyncIterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[routes.database] = override
    try:
        yield
    finally:
        app.dependency_overrides.pop(routes.database, None)
        engine.dispose()


@pytest.mark.anyio
async def test_evaluate_dataset_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: FakeProvider())
    samples = json.loads((ROOT / "docs/poe2-checker-test-items.json").read_text())["samples"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for sample in samples:
            response = await client.post("/api/items/evaluate", json={"raw_text": sample["raw_text"]})
            assert response.status_code == 200, sample["id"]
            body = response.json()
            assert body["evaluation"]["build"]["suitability"] == "unknown_without_profile"
            assert body["local_check"]["facts"]["name"]
            assert body["provider"] == "fake"
            assert body["provider_status"] == "success"
            assert body["parse"]["item"]["raw_text"] == sample["raw_text"]


@pytest.mark.anyio
async def test_openai_provider_uses_structured_parse_and_no_storage() -> None:
    parsed = parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text())
    facts = check_item_facts(parsed.item).facts
    response = SimpleNamespace(
        output_parsed=result(), output=[],
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )
    parse = pytest.importorskip("unittest.mock").AsyncMock(return_value=response)
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    provider = OpenAIEvaluationProvider(
        api_key="not-a-real-key", model="mock-model", reasoning_effort="medium",
        timeout=1, max_retries=0, max_input_chars=20_000, max_output_tokens=500,
        rate_limit_per_minute=2, client=client,
    )
    assert await provider.evaluate(facts) == result()
    kwargs = parse.await_args.kwargs
    assert kwargs["text_format"] is EvaluationResult
    assert kwargs["store"] is False
    assert kwargs["max_output_tokens"] == 500
    assert "raw_text" not in kwargs["input"][0]["content"]


@pytest.mark.anyio
async def test_provider_refusal_and_rate_limit_are_stable() -> None:
    parsed = parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text())
    facts = check_item_facts(parsed.item).facts
    refusal = SimpleNamespace(
        output_parsed=None,
        output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
    )
    parse = pytest.importorskip("unittest.mock").AsyncMock(return_value=refusal)
    provider = OpenAIEvaluationProvider(
        api_key="x", model="mock", reasoning_effort="medium", timeout=1, max_retries=0,
        max_input_chars=20_000, max_output_tokens=50, rate_limit_per_minute=1,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )
    with pytest.raises(EvaluationProviderError, match="provider_refusal"):
        await provider.evaluate(facts)
    with pytest.raises(EvaluationProviderError, match="rate_limited"):
        await provider.evaluate(facts)


@pytest.mark.anyio
async def test_sdk_validation_error_is_normalized() -> None:
    facts = check_item_facts(
        parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text()).item
    ).facts
    invalid = result().model_dump()
    invalid["warnings"] = ["10% stärker"]
    try:
        EvaluationResult.model_validate(invalid)
    except ValidationError as validation_error:
        parse = pytest.importorskip("unittest.mock").AsyncMock(side_effect=validation_error)
    provider = OpenAIEvaluationProvider(
        api_key="x", model="mock", reasoning_effort="medium", timeout=1, max_retries=0,
        max_input_chars=20_000, max_output_tokens=100, rate_limit_per_minute=1,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )
    with pytest.raises(EvaluationProviderError, match="invalid_provider_response"):
        await provider.evaluate(facts)


def test_schema_rejects_exact_damage_percent_and_extra_fields() -> None:
    data = result().model_dump()
    data["build"]["reasons"] = ["12% mehr DPS"]
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)
    data = result().model_dump()
    data["warnings"] = ["Ein Upgrade ist wahrscheinlich."]
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)
    data = result().model_dump()
    data["trade"]["reasons"] = ["DPS steigt um 12,5 %."]
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)
    data = result().model_dump()
    data["score_delta"] = 3
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


@pytest.mark.parametrize("claim", [
    "Das ist eine Aufwertung.",
    "Gegenüber dem aktuellen Item ist es besser.",
    "Schlechter als das ausgerüstete Item.",
    "The score improved by 7 points.",
    "Der Score ist um 4 Punkte gestiegen.",
    "score_delta: 5",
])
def test_schema_rejects_alternate_equipment_comparisons(claim: str) -> None:
    data = result().model_dump()
    data["build"]["reasons"] = [claim]
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


@pytest.mark.anyio
async def test_provider_failure_preserves_typed_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: FailingProvider())
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/items/evaluate", json={"raw_text": raw})
    assert response.status_code == 200
    body = response.json()
    assert body["parse"]["item"]["raw_text"] == raw
    assert body["local_check"]["facts"]["name"]
    assert body["evaluation"] is None
    assert body["provider_status"] == "unavailable"
    assert body["provider_error"] == {"code": "provider_refusal", "message": "Sichere Ablehnung."}


def test_evaluation_settings_are_bounded_and_reasoning_is_typed() -> None:
    with pytest.raises(ValidationError):
        Settings(evaluation_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(evaluation_max_retries=99)
    with pytest.raises(ValidationError):
        Settings(evaluation_rate_limit_per_minute=0)
    with pytest.raises(ValidationError):
        Settings(openai_reasoning_effort="extreme")
    with pytest.raises(ValidationError):
        Settings(openai_model="   ")


@pytest.mark.anyio
async def test_invalid_environment_returns_safe_typed_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_marker = "INVALID_SECRET_DETAIL"
    monkeypatch.setenv("EVALUATION_MAX_RETRIES", secret_marker)
    get_settings.cache_clear()
    get_evaluation_provider.cache_clear()
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/items/evaluate", json={"raw_text": raw})
        assert response.status_code == 200
        body = response.json()
        assert body["provider_error"] == {
            "code": "provider_not_configured",
            "message": "Die AI-Bewertung ist nicht konfiguriert.",
        }
        assert secret_marker not in response.text
        assert body["local_check"]["facts"]["name"]
    finally:
        get_settings.cache_clear()
        get_evaluation_provider.cache_clear()


@pytest.mark.anyio
async def test_usage_log_contains_tokens_but_no_item_or_key(caplog: pytest.LogCaptureFixture) -> None:
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text().replace("Doom", "LEAKMARKER")
    facts = check_item_facts(parse_with_warnings(raw).item).facts
    response = SimpleNamespace(
        output_parsed=result(), output=[],
        usage=SimpleNamespace(input_tokens=123, output_tokens=45),
    )
    parse = pytest.importorskip("unittest.mock").AsyncMock(return_value=response)
    provider = OpenAIEvaluationProvider(
        api_key="SECRETLEAKMARKER", model="mock", reasoning_effort="medium", timeout=1,
        max_retries=0, max_input_chars=20_000, max_output_tokens=100,
        rate_limit_per_minute=1,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )
    with caplog.at_level("INFO"):
        await provider.evaluate(facts)
    assert "input_tokens=123" in caplog.text
    assert "output_tokens=45" in caplog.text
    assert "LEAKMARKER" not in caplog.text
    assert "SECRETLEAKMARKER" not in caplog.text
    assert "cost_estimate=unavailable" in caplog.text  # No model pricing is assumed or invented.
    assert "$" not in caplog.text
