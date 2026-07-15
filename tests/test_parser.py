from pathlib import Path

import pytest

from app.parser import parse_item_text

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.mark.parametrize("name", ["rare_wand.txt", "granted_skill.txt", "roll_range.txt", "no_requirements.txt", "two_sockets.txt"])
def test_parser_is_deterministic_and_preserves_raw_text(name: str) -> None:
    raw = fixture(name)
    first = parse_item_text(raw)
    assert first == parse_item_text(raw)
    assert first.raw_text == raw


def test_rare_wand_has_rune_and_six_affixes() -> None:
    item = parse_item_text(fixture("rare_wand.txt"))
    assert item.name == "Bramble Needle"
    assert sum(mod.source == "explicit" for mod in item.modifiers) == 6
    assert sum(mod.rune for mod in item.modifiers) == 1
    assert next(mod for mod in item.modifiers if mod.name == "of Anarchy").normalized_key == "all_chaos_spell_skill_levels"


def test_granted_skill_is_field_and_modifier() -> None:
    item = parse_item_text(fixture("granted_skill.txt"))
    assert item.granted_skill == "Level 4 Chaos Bolt"
    assert item.modifiers[0].source == "granted_skill"
    assert item.modifiers[0].normalized_key == "unknown"


def test_current_value_and_roll_range() -> None:
    modifier = parse_item_text(fixture("roll_range.txt")).modifiers[0]
    assert modifier.values == [30]
    assert modifier.roll_ranges == [[25, 34]]


def test_missing_requirements_remain_none() -> None:
    item = parse_item_text(fixture("no_requirements.txt"))
    assert item.required_level is None
    assert item.required_strength is None
    assert "+17% to Fire Resistance" not in item.unknown_lines
    assert item.modifiers[-1].normalized_key == "fire_resistance"


def test_two_sockets_and_augmented_defence() -> None:
    item = parse_item_text(fixture("two_sockets.txt"))
    assert item.sockets == ["S", "S"]
    assert item.energy_shield == 206


def test_unknown_lines_keep_original_order() -> None:
    raw = "Item Class: Rings\nRarity: Normal\nIron Ring\nIron Ring\n--------\nMystery text\nAnother mystery"
    item = parse_item_text(raw)
    assert item.unknown_lines == ["Mystery text", "Another mystery"]


def test_compact_requirements_and_magic_identity_do_not_consume_properties() -> None:
    raw = "Item Class: Wands\nRarity: Magic\nChaotic Wand\n--------\nRequires: Level 59, 78 Int\nItem Level: 61"
    item = parse_item_text(raw)
    assert item.name == "Chaotic Wand"
    assert item.base_type is None
    assert item.required_level == 59
    assert item.required_intelligence == 78
    assert item.item_level == 61


def test_crafted_and_desecrated_suffix_headers() -> None:
    raw = """Item Class: Rings
Rarity: Rare
Doom Circle
Ruby Ring
--------
{ Crafted Suffix Modifier \"of Craft\" (Tier: 2) — Resistance }
+20% to Fire Resistance
{ Desecrated Suffix Modifier \"of Ruin\" (Tier: 1) — Chaos }
+9% to Chaos Resistance"""
    item = parse_item_text(raw)
    assert [modifier.source for modifier in item.modifiers] == ["crafted", "desecrated"]
    assert [modifier.affix_type for modifier in item.modifiers] == ["suffix", "suffix"]


def test_multiline_affix_copies_header_metadata_to_each_line() -> None:
    raw = """Item Class: Gloves
Rarity: Unique
Example Grip
Silk Gloves
--------
{ Unique Modifier \"Example effect\" — Caster }
100% increased Spell Damage
20% reduced Cast Speed"""
    modifiers = parse_item_text(raw).modifiers
    assert len(modifiers) == 2
    assert all(modifier.name == "Example effect" for modifier in modifiers)
    assert all(modifier.tags == ["Caster"] for modifier in modifiers)


def test_augmented_defence_flags_are_explicit() -> None:
    raw = """Item Class: Body Armours
Rarity: Normal
Vest
--------
Armour: 10 (augmented)
Evasion: 20
Energy Shield: 30 (augmented)"""
    item = parse_item_text(raw)
    assert item.armour_augmented is True
    assert item.evasion_augmented is False
    assert item.energy_shield_augmented is True
