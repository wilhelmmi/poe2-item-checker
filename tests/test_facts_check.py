import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.facts.engine import check_item_facts
from app.facts.config import FACTS_CONFIG
from app.facts.engine import _match_rule
from app.facts.extraction import extract_item_facts
from app.facts.schemas import FactsConfig, TradeRule
from app.main import app
from app.parser import parse_item_text

ROOT = Path(__file__).parents[1]
SAMPLES = {sample["id"]: sample for sample in json.loads(
    (ROOT / "docs/poe2-checker-test-items.json").read_text()
)["samples"]}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize(("sample_id", "trade", "crafting"), [
    ("magic_ashen_staff", "vendor", "needs_review"),
    ("magic_30ms_boots", "test_1_ex", "needs_review"),
    ("rare_vile_robe", "price_check", "needs_review"),
    ("magic_vile_robe_spirit", "test_1_ex", "needs_review"),
    ("magic_dueling_wand_lightning", "vendor", "needs_review"),
])
def test_documented_rules(sample_id: str, trade: str, crafting: str) -> None:
    check = check_item_facts(parse_item_text(SAMPLES[sample_id]["raw_text"]))
    assert check.trade.outcome == trade
    assert check.crafting.outcome == crafting
    assert check.disclaimer
    assert check == check_item_facts(parse_item_text(SAMPLES[sample_id]["raw_text"]))


def test_staff_facts_and_roll_position() -> None:
    check = check_item_facts(parse_item_text(SAMPLES["magic_ashen_staff"]["raw_text"]))
    assert check.facts.slot_hint == "staff"
    lightning = next(mod for mod in check.facts.modifiers if mod.normalized_key == "extra_lightning_damage")
    assert lightning.current_values == [44]
    assert lightning.roll_ranges == [[43, 48]]
    assert lightning.roll_position == pytest.approx(0.2)
    assert check.trade.confidence == "high"
    assert check.trade.evidence[0].rule_id == "trade.staff_fixture.vendor"


def test_unique_and_unknown_fall_back_without_generic_vendor_rule() -> None:
    raw = """Item Class: Gloves
Rarity: Unique
Unknown Grip
Silk Gloves
--------
Item Level: 1
--------
{ Unique Modifier }
Uncatalogued effect"""
    check = check_item_facts(parse_item_text(raw))
    assert check.trade.outcome == "manual_review"
    assert check.trade.confidence == "low"
    assert check.crafting.outcome == "needs_review"
    assert "unknown_modifiers_present" in check.warnings


def test_config_rejects_unknown_schema_and_fields() -> None:
    with pytest.raises(ValidationError):
        FactsConfig.model_validate({"schema_version": 2, "extra": True})
    duplicate_priority = FACTS_CONFIG.model_dump()
    duplicate_priority["trade_rules"][1]["priority"] = duplicate_priority["trade_rules"][0]["priority"]
    with pytest.raises(ValidationError):
        FactsConfig.model_validate(duplicate_priority)


def test_staff_name_without_documented_modifiers_falls_back() -> None:
    raw = """Item Class: Staves
Rarity: Magic
Vorpal Ashen Staff of Siphoning
--------
Item Level: 66
--------
{ Prefix Modifier }
30% increased Spell Damage"""
    assert check_item_facts(parse_item_text(raw)).trade.outcome == "manual_review"


def test_unknown_explicit_modifier_caps_otherwise_known_rule() -> None:
    raw = SAMPLES["magic_30ms_boots"]["raw_text"] + "\n{ Suffix Modifier }\nUncatalogued defence"
    check = check_item_facts(parse_item_text(raw))
    assert check.trade.outcome == "manual_review"
    assert check.crafting.outcome == "needs_review"


def test_item_facts_are_complete_observable_projection() -> None:
    facts = extract_item_facts(parse_item_text(SAMPLES["rare_vile_robe"]["raw_text"]))
    assert facts.required_level == 65
    assert facts.required_intelligence == 121
    assert facts.sockets == ["S", "S"]
    assert facts.energy_shield == 206
    assert facts.energy_shield_augmented is True
    assert facts.modifiers[0].source == "explicit"
    assert facts.modifiers[0].tier == 8
    assert facts.modifiers[0].tags == ["Energy Shield"]


def test_modifier_group_requires_same_modifier() -> None:
    raw = """Item Class: Boots
Rarity: Magic
Slow Boots
--------
{ Prefix Modifier }
20% increased Movement Speed
{ Suffix Modifier }
+30% to Cold Resistance"""
    facts = extract_item_facts(parse_item_text(raw))
    rule = TradeRule(
        id="test.group", priority=1, source="test", outcome="test_1_ex", confidence="low",
        message="test", predicates=[
            {"scope":"modifier","field":"normalized_key","op":"eq","value":"movement_speed","modifier_group":"speed"},
            {"scope":"modifier","field":"current_value","op":"gte","value":30,"modifier_key":"movement_speed","modifier_group":"speed"},
        ],
    )
    assert _match_rule(rule, facts) is None


def test_roll_positions_are_not_clamped_and_invalid_ranges_warn() -> None:
    raw = """Item Class: Boots
Rarity: Magic
Odd Boots
--------
{ Prefix Modifier }
50(10-20)% increased Movement Speed
{ Suffix Modifier }
+15(20-10)% to Cold Resistance"""
    facts = extract_item_facts(parse_item_text(raw))
    assert facts.modifiers[0].roll_position == 4
    assert "roll_position_out_of_range" in facts.warnings
    assert "roll_range_reversed" in facts.warnings


@pytest.mark.anyio
async def test_check_endpoint_complete_incomplete_and_idempotent() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        raw = SAMPLES["magic_ashen_staff"]["raw_text"]
        first = await client.post("/api/items/check", json={"raw_text": raw})
        second = await client.post("/api/items/check", json={"raw_text": raw})
        assert first.status_code == 200
        assert first.json() == second.json()
        assert first.json()["assessment"]["trade"]["outcome"] == "vendor"
        collapsed = (ROOT / "docs/example-items.txt").read_text()
        skipped = (await client.post("/api/items/check", json={"raw_text": collapsed})).json()
        assert skipped["assessment"] is None
        assert "assessment_skipped" in {warning["code"] for warning in skipped["parse"]["warnings"]}
