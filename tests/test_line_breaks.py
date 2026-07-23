from pathlib import Path

import pytest

from app.parser.item_text import parse_item_text
from app.parser.line_breaks import suggest_line_breaks

ROOT = Path(__file__).parents[1]


def _remove_insertions(suggested: str, offsets: list[int]) -> str:
    offset_set = set(offsets)
    original_index = 0
    restored: list[str] = []
    for character in suggested:
        if character == "\n" and original_index in offset_set:
            offset_set.remove(original_index)
            continue
        restored.append(character)
        original_index += 1
    return "".join(restored)


def test_example_suggestion_is_insert_only_deterministic_and_parseable() -> None:
    raw = (ROOT / "docs/example-items.txt").read_text()
    suggestion = suggest_line_breaks(raw)
    assert suggestion is not None
    assert suggestion == suggest_line_breaks(raw)
    offsets = [insertion.offset for insertion in suggestion.insertions]
    assert offsets == sorted(set(offsets))
    assert _remove_insertions(suggestion.suggested_text, offsets) == raw
    item = parse_item_text(suggestion.suggested_text)
    assert (item.item_class, item.rarity, item.name) == (
        "Staves", "Magic", "Vorpal Ashen Staff of Siphoning"
    )
    assert (item.required_level, item.item_level, item.granted_skill) == (44, 66, "Level 14 Firebolt")
    modifiers = [modifier for modifier in item.modifiers if modifier.source == "explicit"]
    assert len(modifiers) == 2
    assert modifiers[0].tier == 3
    assert modifiers[0].tags == ["Damage", "Elemental", "Lightning"]
    assert modifiers[0].values == [44]
    assert modifiers[0].roll_ranges == [[43, 48]]


@pytest.mark.parametrize("raw", [
    "Item Class: Rings\nRarity: Normal\nIron Ring",
    "plain text without markers",
    "text ------- text",
    "text --------- text",
    "text { arbitrary braces } text",
    'text { Prefix Modifier "broken" text',
    "Gain 44(43-48)% of Damage as Extra Lightning Damage",
    "prefix Item Class: Staves Rarity: Magic { Prefix Modifier }",
    "Item Class: Staves Rarity: nonsense Rarity: Magic -------- rest",
    "Item Class:     Rarity: Magic -------- rest",
])
def test_unsafe_or_irrelevant_input_has_no_suggestion(raw: str) -> None:
    assert suggest_line_breaks(raw) is None


def test_leading_trailing_whitespace_and_dense_markers_keep_original_offsets() -> None:
    raw = "  Item Class: Rings Rarity: Normal -------- -------- Iron Ring  "
    suggestion = suggest_line_breaks(raw)
    assert suggestion is not None
    offsets = [insertion.offset for insertion in suggestion.insertions]
    assert offsets == sorted(set(offsets))
    assert _remove_insertions(suggestion.suggested_text, offsets) == raw
    assert suggestion.suggested_text.startswith("  Item Class:")
    assert suggestion.suggested_text.endswith("Iron Ring  ")


def test_terminal_line_break_is_already_multiline_for_suggestion_purposes() -> None:
    assert suggest_line_breaks("Item Class: Rings Rarity: Normal\n") is None


def test_valid_modifier_header_in_unanchored_free_text_is_ignored() -> None:
    raw = 'notes { Prefix Modifier "Vorpal" (Tier: 3) — Damage } more'
    assert suggest_line_breaks(raw) is None


def test_collapsed_rare_name_and_focus_base_are_separated_insert_only() -> None:
    raw = (
        "Item Class: Foci Rarity: Rare Empyrean Emblem Runed Focus -------- "
        "Energy Shield: 83 (augmented) -------- Item Level: 67"
    )
    suggestion = suggest_line_breaks(raw)
    assert suggestion is not None
    assert "Empyrean Emblem\n Runed Focus" in suggestion.suggested_text
    offsets = [insertion.offset for insertion in suggestion.insertions]
    assert _remove_insertions(suggestion.suggested_text, offsets) == raw
    item = parse_item_text(suggestion.suggested_text)
    assert (item.name, item.base_type) == ("Empyrean Emblem", "Runed Focus")


def test_collapsed_german_export_is_recognized_and_parseable() -> None:
    raw = (
        "Gegenstandsklasse: Stiefel Seltenheit: Magisch Schnelle Seidenstiefel -------- "
        "Gegenstandsstufe: 66 -------- { Präfix-Modifikator (Rang: 3) — Tempo } "
        "30% erhöhte Bewegungsgeschwindigkeit"
    )
    suggestion = suggest_line_breaks(raw)
    assert suggestion is not None
    item = parse_item_text(suggestion.suggested_text)
    assert (item.item_class, item.rarity, item.item_level) == ("Boots", "Magic", 66)
    assert item.modifiers[0].normalized_key == "movement_speed"
