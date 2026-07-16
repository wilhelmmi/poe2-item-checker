import json
from pathlib import Path

import pytest

from app.buildfit.config import BUILD_FIT_CONFIG, BuildFitConfig
from app.buildfit.engine import classify_delta, compare_slots, delta_band, score_item
from app.db.models import CharacterProfile
from app.parser.service import parse_with_warnings
from app.schemas.items import ModifierData, ParsedItem

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(("delta", "expected"), [
    (-12, "downgrade"), (-11, "downgrade"), (-5, "downgrade"),
    (-4, "sidegrade"), (4, "sidegrade"), (5, "conditional_upgrade"),
    (11, "conditional_upgrade"), (12, "upgrade"),
])
def test_delta_boundaries(delta: int, expected: str) -> None:
    assert classify_delta(delta) == expected


@pytest.mark.parametrize(("delta", "expected"), [
    (-12, "major_downgrade"), (-11, "negative"), (-5, "negative"),
    (-4, "sidegrade"), (4, "sidegrade"), (5, "positive"),
    (11, "positive"), (12, "major_upgrade"),
])
def test_delta_band_boundaries(delta: int, expected: str) -> None:
    assert delta_band(delta) == expected


def test_build_fit_config_is_strict_and_versioned() -> None:
    assert BUILD_FIT_CONFIG.schema_version == 1
    with pytest.raises(ValueError):
        BuildFitConfig.model_validate({**BUILD_FIT_CONFIG.model_dump(), "extra": True})
    for mutation in (
        {"modifier_weights": {**BUILD_FIT_CONFIG.modifier_weights, "typo": 1}},
        {"slot_multipliers": {"typo": {}}},
        {"defence_caps": {"energy_shield": 1}},
        {"modifier_weights": {**BUILD_FIT_CONFIG.modifier_weights, "increased_spell_damage": 999}},
        {"slot_multipliers": {"wand": {"increased_spell_damage": float("inf")}}},
    ):
        with pytest.raises(ValueError):
            BuildFitConfig.model_validate({**BUILD_FIT_CONFIG.model_dump(), **mutation})


def test_documented_items_score_deterministically_in_range() -> None:
    samples = json.loads((ROOT / "docs/poe2-checker-test-items.json").read_text())["samples"]
    slots = {"Boots": "boots", "Body Armours": "body_armour", "Wands": "wand",
             "Rings": "ring_1", "Gloves": "gloves", "Helmets": "helmet",
             "Belts": "belt", "Amulets": "amulet", "Foci": "focus"}
    for sample in samples:
        item = parse_with_warnings(sample["raw_text"]).item
        if item.item_class not in slots:
            continue
        first = score_item(item, slots[item.item_class])
        assert first == score_item(item, slots[item.item_class])
        assert 0 <= first.score <= 100


def test_energy_shield_total_is_counted_once_as_defence_evidence() -> None:
    item = parse_with_warnings((ROOT / "tests/fixtures/rare_wand.txt").read_text()).item
    data = item.model_copy(update={"energy_shield": 200})
    evidence = score_item(data, "focus").evidence
    assert sum(value.rule_id == "defence.energy_shield" for value in evidence) == 1
    assert not any(value.rule_id == "modifier.maximum_energy_shield" for value in evidence)


@pytest.mark.parametrize("key", ["all_chaos_spell_skill_levels", "reduced_cast_speed"])
def test_clamp_evidence_keeps_sum_invariant(key: str) -> None:
    modifiers = [ModifierData(source="explicit", raw_text=key, normalized_key=key, values=[1]) for _ in range(8)]
    scored = score_item(ParsedItem(raw_text="x", name="x", modifiers=modifiers), "wand")
    assert sum(value.points for value in scored.evidence) == scored.score
    assert any(value.rule_id == "score.clamp" for value in scored.evidence)


def test_unknown_modifier_changes_completeness_not_score() -> None:
    clean = ParsedItem(raw_text="x", name="x")
    unknown = clean.model_copy(update={"modifiers": [ModifierData(source="explicit", raw_text="mystery")]})
    assert score_item(clean, "wand").score == score_item(unknown, "wand").score
    assert score_item(unknown, "wand").completeness == "partial"


def test_doedre_has_positive_spell_and_bounded_negative_cast_speed_evidence() -> None:
    samples = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    item = parse_with_warnings(samples["equipment_raw_text"]["gloves"]).item
    scored = score_item(item, "gloves")
    evidence = {value.rule_id: value.points for value in scored.evidence}
    assert evidence["modifier.increased_spell_damage"] > 0
    assert -30 <= evidence["modifier.reduced_cast_speed"] < 0
    assert sum(value.points for value in scored.evidence) == scored.score


@pytest.mark.parametrize("slot", ["wand", "helmet"])
def test_seed_evidence_ids_are_unique_and_sum_to_score(slot: str) -> None:
    seed = json.loads((ROOT / "docs/poe2-current-equipment.seed.json").read_text())
    item = parse_with_warnings(seed["equipment_raw_text"][slot]).item
    scored = score_item(item, slot)
    ids = [value.rule_id for value in scored.evidence]
    assert len(ids) == len(set(ids))
    assert sum(value.points for value in scored.evidence) == scored.score


def test_remaining_equipment_requirement_failure_overrides_positive_score() -> None:
    old = ParsedItem(raw_text="old", item_class="Amulets", name="Old", modifiers=[
        ModifierData(source="explicit", raw_text="+20 Int", normalized_key="intelligence", values=[20])
    ])
    candidate = ParsedItem(raw_text="new", item_class="Amulets", name="New", modifiers=[
        ModifierData(source="explicit", raw_text="+1 chaos", normalized_key="all_chaos_spell_skill_levels", values=[1])
    ])
    helmet = ParsedItem(raw_text="helmet", item_class="Helmets", name="Helmet", required_intelligence=100)
    profile = CharacterProfile(id=1, name="test", intelligence=100, resistance_cap=75, notes="")
    result = compare_slots(candidate, ["amulet"], {"amulet": old, "helmet": helmet}, {"amulet", "helmet"}, profile)
    comparison = result.comparisons[0]
    assert comparison.candidate.score > comparison.equipped.score
    assert comparison.category == "not_suitable"
    assert any(check.code == "remaining_helmet_intelligence" and check.status == "fail"
               for check in comparison.hard_checks.checks)
