import asyncio
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
from app.builds.registry import DEFAULT_BUILD_ID
from app.db.models import Base
from app.db.session import enable_sqlite_foreign_keys
from app.equipment.service import replace_equipment
from app.evaluation.openai_provider import OpenAIEvaluationProvider
from app.evaluation.provider import EvaluationProviderError
from app.evaluation.schemas import EvaluationInput, EvaluationResult
from app.main import app
from tests.build_seed import seed_builtin_builds

ROOT = Path(__file__).parents[1]


def result() -> EvaluationResult:
    return EvaluationResult(
        recommendation="better", confidence="high", reasons=["Relevant."], warnings=[],
        verdict="upgrade", current_item_name="Alt", new_item_name="Neu",
        gains=["Mehr relevante Werte."], losses=[],
        impacts={"damage": "better", "defensive": "similar", "resistances": "similar", "utility": "similar"},
        clear_recommendation="Neues Item ausrüsten.",
    )


def test_unknown_modifier_resolution_is_bounded_and_conservative() -> None:
    from unittest.mock import AsyncMock

    parse = AsyncMock(return_value=SimpleNamespace(output_parsed={
        "resolutions": [
            {"modifier_index": 2, "normalized_key": "fire_resistance", "confidence": "high"},
            {"modifier_index": 3, "normalized_key": "maximum_life", "confidence": "medium"},
            {"modifier_index": 4, "normalized_key": "maximum_life", "confidence": "high"},
            {"modifier_index": 4, "normalized_key": "maximum_mana", "confidence": "high"},
        ]
    }))
    provider = OpenAIEvaluationProvider(
        api_key="test", model="test-model", reasoning_effort="low", timeout=1,
        max_retries=0, max_input_chars=20_000, max_output_tokens=3_000,
        rate_limit_per_minute=1,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )

    resolved = asyncio.run(provider.resolve_unknown_modifiers([
        (2, "Feuerwiderstand " + "x" * 600),
        (3, "maximales Leben"),
        (4, "mehr von irgendetwas"),
    ]))

    assert resolved == [{
        "modifier_index": 2, "normalized_key": "fire_resistance", "confidence": "high"
    }]
    request = parse.await_args.kwargs
    assert request["store"] is False
    payload = json.loads(request["input"][0]["content"])
    assert len(payload["unknown_german_modifiers"][0]["raw_text"]) == 500
    assert len(provider.limiter._calls) == 0
    assert len(provider.resolution_limiter._calls) == 1
    assert asyncio.run(provider.resolve_unknown_modifiers([(2, "Feuerwiderstand")])) == []
    assert parse.await_count == 1
    assert len(provider.limiter._calls) == 0


def test_german_item_locale_uses_headers_not_modifier_vocabulary() -> None:
    from app.parser.localization import is_german_item_text

    assert is_german_item_text(
        "Gegenstandsklasse: Zauberstäbe\nSeltenheit: Selten\n+9 zu etwas völlig Neuem"
    )
    assert not is_german_item_text(
        "Item Class: Wands\nRarity: Rare\n+9 to something entirely new"
    )


@pytest.mark.parametrize(
    "claim",
    [
        "12 % mehr DPS.",
        "15% stärker als das ausgerüstete Item.",
        "15% better than equipped.",
        "The item deals 20% more damage than equipped.",
        "Das Item verursacht 20% mehr Schaden als das ausgerüstete Item.",
        "DPS improves by twelve percent.",
        "The gain is 15 percent compared with equipped.",
        "The gain is 15 percent.",
        "15% performance improvement.",
        "Der Score steigt.",
        "Marktwert: ein Divine.",
        "Trade value is one Divine.",
        "Market value is high.",
        "Sell this item.",
        "Vendor it.",
        "Das Item sollte verkauft werden.",
        "Das Item sollte gecraftet werden.",
        "Den Modifier neu craften.",
        "The item should be crafted.",
        "This can be crafted further.",
        "Get this crafted.",
        "Add a crafted modifier.",
        "Use a crafted modifier.",
        "The crafted modifier should be removed.",
        "The item has a crafted modifier; remove it.",
        "Use an Essence.",
        "Apply an Omen.",
        "Annul the suffix.",
        "Socket a rune.",
    ],
)
def test_result_rejects_out_of_scope_claims(claim: str) -> None:
    with pytest.raises(ValidationError):
        EvaluationResult(recommendation="better", confidence="high", reasons=[claim], warnings=[], verdict="upgrade", current_item_name="Alt", new_item_name="Neu", gains=[], losses=[], impacts={"damage":"better","defensive":"similar","resistances":"similar","utility":"similar"}, clear_recommendation="Ausrüsten.")


@pytest.mark.parametrize(
    "claim",
    [
        "Essenzentzug profitiert von Chaos-Skill-Leveln.",
        "Das Item hat 26% increased Cast Speed.",
        "The item has 15% more Chaos Damage.",
        "The item has 10% less damage taken.",
        "Der Ring liefert 30% Lightning Resistance.",
        "Der Modifier gibt 20% chance for ES Recharge.",
        "Gewinn: 44% of Damage as Extra Lightning Damage gegenüber dem ausgerüsteten Item.",
        "Verlust: Das alte Item liefert 30% Lightning Resistance.",
        "Das neue Item mit 26% increased Cast Speed ausrüsten.",
        "Direkter Trade-off: 20% Cast Speed statt 30% Lightning Resistance.",
        "Trade-off: mehr Energy Shield, aber keine Mana-Regeneration.",
        "The item has a crafted modifier granting Cast Speed.",
        "Der gecraftete Modifier gewährt Cast Speed.",
        "The suffix is crafted.",
    ],
)
def test_result_allows_observed_facts_and_tradeoffs(claim: str) -> None:
    value = EvaluationResult(
        recommendation="better",
        confidence="high",
        reasons=[claim],
        warnings=[],
        verdict="upgrade", current_item_name="Alt", new_item_name="Neu", gains=[], losses=[],
        impacts={"damage":"better","defensive":"similar","resistances":"similar","utility":"similar"},
        clear_recommendation="Ausrüsten.",
    )
    assert value.recommendation == "better"


@pytest.mark.parametrize(
    ("field", "claim"),
    [
        ("gains", "Gewinn: 26% increased Cast Speed statt 15% auf dem alten Item."),
        ("losses", "Verlust: 30% Lightning Resistance vom alten Ring."),
        ("clear_recommendation", "Wegen 26% Cast Speed trotz Resistenzverlust ausrüsten."),
    ],
)
def test_result_allows_observed_percent_tradeoffs_in_rich_fields(field: str, claim: str) -> None:
    data = result().model_dump()
    data[field] = claim if field == "clear_recommendation" else [claim]
    assert EvaluationResult.model_validate(data).recommendation == "better"


def test_result_requires_consistent_verdict() -> None:
    data = result().model_dump()
    data["verdict"] = "downgrade"
    with pytest.raises(ValidationError, match="verdict must match recommendation"):
        EvaluationResult.model_validate(data)


def test_new_free_text_fields_receive_compliance_validation() -> None:
    data = result().model_dump()
    data["clear_recommendation"] = "Dieses Item für ein Divine verkaufen."
    with pytest.raises(ValidationError, match="Marktwertaussagen"):
        EvaluationResult.model_validate(data)


@pytest.mark.parametrize("field", ["reasons", "warnings", "gains", "losses"])
def test_explanation_entries_are_bounded(field: str) -> None:
    data = result().model_dump()
    data[field] = ["x" * 501]
    with pytest.raises(ValidationError, match="at most 500 characters"):
        EvaluationResult.model_validate(data)


def test_evaluation_input_rejects_inconsistent_slot_context() -> None:
    from app.builds.registry import DEFAULT_BUILD_ID, get_build
    from app.parser.service import parse_with_warnings

    item = parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text()).item
    with pytest.raises(ValidationError, match="equipped_slots must exactly match target_slots"):
        EvaluationInput(
            candidate=item, equipped=item, target_slot="wand", target_slots=["wand"],
            equipped_slots={"focus": item}, observed_profile=None, build=get_build(DEFAULT_BUILD_ID),
        )


class FakeProvider:
    name = "fake"
    model = "mock-model"

    def __init__(self) -> None:
        self.received: EvaluationInput | None = None

    async def evaluate(self, evaluation_input: EvaluationInput) -> EvaluationResult:
        self.received = evaluation_input
        return result()


class AlternativeProvider(FakeProvider):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target

    async def evaluate(self, evaluation_input: EvaluationInput) -> EvaluationResult:
        self.received = evaluation_input
        return result().model_copy(update={"recommended_target_slot": self.target})


class FailingProvider(FakeProvider):
    async def evaluate(self, evaluation_input: EvaluationInput) -> EvaluationResult:
        raise EvaluationProviderError("provider_refusal", "Sichere Ablehnung.")


class ResolvingProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.unknown: list[tuple[int, str]] = []

    async def resolve_unknown_modifiers(
        self, modifiers: list[tuple[int, str]]
    ) -> list[dict[str, object]]:
        self.unknown = modifiers
        selected = next(value for value in modifiers if value[1] == "+9 zu völlig Neuem")
        return [{
            "modifier_index": selected[0],
            "normalized_key": "maximum_life",
            "confidence": "high",
        }]


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
    with factory() as db:
        seed_builtin_builds(db)

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
async def test_evaluate_resolves_unknown_modifier_from_german_item_locale(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = ResolvingProvider()
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    raw = (ROOT / "tests/fixtures/rare_wand_de.txt").read_text() + "\n+9 zu völlig Neuem"
    equipped = (ROOT / "tests/fixtures/rare_wand.txt").read_text()
    with isolated_db() as db:
        replace_equipment(db, "wand", equipped)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": raw, "target_slot": "wand"}
        )

    assert response.status_code == 200
    assert any(raw_text == "+9 zu völlig Neuem" for _, raw_text in provider.unknown)
    resolution = response.json()["modifier_resolutions"][0]
    modifier = response.json()["parse"]["item"]["modifiers"][resolution["modifier_index"]]
    assert modifier["raw_text"] == "+9 zu völlig Neuem"
    assert modifier["values"] == [9.0]
    assert modifier["normalized_key"] == "maximum_life"


@pytest.mark.anyio
async def test_collapsed_quoted_staff_compares_both_hand_slots(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    with isolated_db() as db:
        replace_equipment(db, "wand", seed["equipment_raw_text"]["wand"])
        replace_equipment(db, "focus", seed["equipment_raw_text"]["focus"])
    collapsed = (
        '"Item Class: Staves Rarity: Magic Vorpal Ashen Staff of Siphoning -------- '
        'Requires: Level 44 -------- Item Level: 66 -------- Grants Skill: Level 14 Firebolt '
        '-------- { Prefix Modifier "Vorpal" (Tier: 3) — Damage, Elemental, Lightning } '
        'Gain 44(43-48)% of Damage as Extra Lightning Damage '
        '{ Suffix Modifier "of Siphoning" (Tier: 3) — Mana } '
        'Gain 23(21-27) Mana per enemy killed"'
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        parsed = await client.post("/api/items/parse", json={"raw_text": collapsed})
        assert parsed.json()["auto_format_status"] == "safe"
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": collapsed, "target_slot": "wand"}
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parse"]["item"]["item_class"] == "Staves"
    assert body["target_slots"] == ["wand", "focus"]
    assert set(provider.received.equipped_slots) == {"wand", "focus"}
    assert provider.received.equipped_slots["wand"] is not None
    assert provider.received.equipped_slots["focus"] is not None


@pytest.mark.anyio
async def test_ring_candidate_compares_both_rings_and_selects_provider_target(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = AlternativeProvider("ring_2")
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text().replace(
        "Item Class: Wands", "Item Class: Rings"
    )
    with isolated_db() as db:
        replace_equipment(db, "ring_1", raw)
        replace_equipment(db, "ring_2", raw)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/items/evaluate", json={"raw_text": raw, "target_slot": "ring_1"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["comparison_slots"] == ["ring_1", "ring_2"]
    assert body["target_slots"] == ["ring_2"]
    assert body["target_slot"] == "ring_2"
    assert set(provider.received.equipped_slots) == {"ring_1", "ring_2"}


@pytest.mark.anyio
async def test_charm_candidate_respects_conservative_one_slot_capacity(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = AlternativeProvider("charm_1")
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text().replace(
        "Item Class: Wands", "Item Class: Charms"
    )
    unknown_belt = (ROOT / "tests/fixtures/rare_wand.txt").read_text().replace(
        "Item Class: Wands", "Item Class: Belts"
    )
    with isolated_db() as db:
        replace_equipment(db, "belt", unknown_belt)
        replace_equipment(db, "charm_1", raw)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/items/evaluate", json={"raw_text": raw, "target_slot": "charm_1"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["comparison_slots"] == ["charm_1"]
    assert body["available_target_slots"] == ["charm_1"]
    assert body["target_slots"] == ["charm_1"]
    assert body["target_slot"] == "charm_1"
    assert body["evaluation"]["verdict"] == "upgrade"
    assert body["evaluation"]["recommendation"] == "better"
    assert body["evaluation"]["recommended_target_slot"] == "charm_1"
    assert provider.received is not None
    assert provider.received.equipped is not None


@pytest.mark.anyio
async def test_locked_charm_target_is_rejected_before_evaluation(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = AlternativeProvider("charm_2")
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text().replace(
        "Item Class: Wands", "Item Class: Charms"
    )
    with isolated_db() as db:
        replace_equipment(db, "charm_1", raw)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/items/evaluate", json={"raw_text": raw, "target_slot": "charm_2"}
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "charm_slot_locked"
    assert provider.received is None


@pytest.mark.anyio
async def test_two_slot_belt_makes_second_charm_an_empty_target(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = AlternativeProvider("charm_2")
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text().replace(
        "Item Class: Wands", "Item Class: Charms"
    )
    belt = (ROOT / "tests/fixtures/rare_wand.txt").read_text().replace(
        "Item Class: Wands", "Item Class: Belts"
    ) + "\nHas 2 Charm Slots"
    with isolated_db() as db:
        replace_equipment(db, "belt", belt)
        replace_equipment(db, "charm_1", raw)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/items/evaluate", json={"raw_text": raw, "target_slot": "charm_1"})
    assert response.status_code == 200, response.text
    assert response.json()["comparison_slots"] == ["charm_1", "charm_2"]
    assert response.json()["available_target_slots"] == ["charm_1", "charm_2"]
    assert response.json()["target_slot"] == "charm_2"
    assert response.json()["provider"] == "system"
    assert provider.received is None


@pytest.mark.anyio
async def test_first_ring_can_be_evaluated_and_equipped_into_empty_loadout(
    monkeypatch: pytest.MonkeyPatch, isolated_db: sessionmaker[Session]
) -> None:
    provider = AlternativeProvider("ring_1")
    monkeypatch.setattr(routes, "get_evaluation_provider", lambda: provider)
    raw = (ROOT / "tests/fixtures/rare_wand.txt").read_text().replace(
        "Item Class: Wands", "Item Class: Rings"
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        evaluated = await client.post("/api/items/evaluate", json={"raw_text": raw, "target_slot": "ring_1"})
        assert evaluated.status_code == 200, evaluated.text
        assert evaluated.json()["equipped"] is None
        assert evaluated.json()["evaluation"]["verdict"] == "upgrade"
        assert evaluated.json()["evaluation"]["losses"] == []
        assert provider.received is None
        equipped = await client.post(
            f"/api/builds/{DEFAULT_BUILD_ID}/equipment/equip",
            json={"raw_text": raw, "target_slot": evaluated.json()["target_slot"]},
        )
    assert equipped.status_code == 200, equipped.text
    assert equipped.json()["slots"]["ring_1"] is not None
    assert equipped.json()["slots"]["ring_2"] is None


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
    comparison = json.loads(content)["comparison"]
    assert "candidate" in comparison and "equipped_slots" in comparison and "build" in comparison
    assert "equipped" not in comparison
    assert '"raw_text"' not in content
    assert '"unknown_lines"' not in content
    assert '"notes"' not in content


@pytest.mark.anyio
async def test_staff_provider_payload_uses_only_sanitized_canonical_slots() -> None:
    from app.builds.registry import DEFAULT_BUILD_ID, get_build
    from app.parser.service import parse_with_warnings

    item = parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text()).item
    data = EvaluationInput(
        candidate=item,
        equipped=item,
        equipped_slots={"wand": item, "focus": item},
        target_slot="wand",
        target_slots=["wand", "focus"],
        observed_profile=None,
        build=get_build(DEFAULT_BUILD_ID),
    )
    parse = pytest.importorskip("unittest.mock").AsyncMock(
        return_value=SimpleNamespace(output_parsed=result(), output=[], usage=None)
    )
    provider = OpenAIEvaluationProvider(
        api_key="x", model="mock", reasoning_effort="medium", timeout=1,
        max_retries=0, max_input_chars=50_000, max_output_tokens=100,
        rate_limit_per_minute=2,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )
    await provider.evaluate(data)
    comparison = json.loads(parse.await_args.kwargs["input"][0]["content"])["comparison"]
    assert comparison["target_slots"] == ["wand", "focus"]
    assert set(comparison["equipped_slots"]) == {"wand", "focus"}
    assert "equipped" not in comparison
    for slot_item in comparison["equipped_slots"].values():
        assert slot_item is not None
        assert "raw_text" not in slot_item
        assert "unknown_lines" not in slot_item


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
async def test_sdk_validation_error_is_normalized_without_log_leakage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.builds.registry import DEFAULT_BUILD_ID, get_build
    from app.parser.service import parse_with_warnings

    marker = "SECRET_VALIDATION_INPUT_MARKER"
    try:
        EvaluationResult.model_validate(
            {
                "recommendation": "better",
                "confidence": "high",
                "reasons": [f"{marker}: 12% mehr DPS"],
                "warnings": [],
                "verdict": "upgrade", "current_item_name": "Alt", "new_item_name": "Neu",
                "gains": [], "losses": [],
                "impacts": {"damage":"better","defensive":"similar","resistances":"similar","utility":"similar"},
                "clear_recommendation": "Ausrüsten.",
            }
        )
    except ValidationError as validation_error:
        sdk_error = validation_error
    item = parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text()).item
    data = EvaluationInput(
        candidate=item,
        equipped=item,
        target_slot="wand",
        observed_profile=None,
        build=get_build(DEFAULT_BUILD_ID),
    )
    parse = pytest.importorskip("unittest.mock").AsyncMock(side_effect=sdk_error)
    provider = OpenAIEvaluationProvider(
        api_key="SECRET_API_KEY_MARKER",
        model="mock",
        reasoning_effort="medium",
        timeout=1,
        max_retries=0,
        max_input_chars=50_000,
        max_output_tokens=100,
        rate_limit_per_minute=2,
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )
    with caplog.at_level("WARNING"):
        with pytest.raises(EvaluationProviderError, match="invalid_provider_response"):
            await provider.evaluate(data)
    assert "phase=sdk_parse" in caplog.text
    assert "error_count=1" in caplog.text
    assert "evaluation_claim_relative_performance" in caplog.text
    assert marker not in caplog.text
    assert "SECRET_API_KEY_MARKER" not in caplog.text
    assert "12%" not in caplog.text


def test_validation_log_redacts_unknown_field_names(caplog: pytest.LogCaptureFixture) -> None:
    from app.evaluation.openai_provider import _log_validation_error

    marker = "SECRET_FIELD_NAME_MARKER"
    with pytest.raises(ValidationError) as captured:
        EvaluationResult.model_validate({
            "recommendation": "better", "confidence": "high",
            "reasons": ["Observed item fact."], "warnings": [], marker: "value",
        })
    with caplog.at_level("WARNING"):
        _log_validation_error("sdk_parse", captured.value)
    assert marker not in caplog.text
    assert "<redacted>" in caplog.text


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
    assert any(build["build_id"].endswith("-v2") for build in builds.json())


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
