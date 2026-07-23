from app.parser.normalizations import NORMALIZATION_REGISTRY_VERSION, normalize_modifier


def test_registry_is_versioned_and_matches_briefing_phrases() -> None:
    assert NORMALIZATION_REGISTRY_VERSION == 2
    assert normalize_modifier("30% increased Movement Speed") == "movement_speed"
    assert normalize_modifier("+29% to Fire Resistance") == "fire_resistance"
    assert normalize_modifier("30% erhöhter Zauberschaden") == "increased_spell_damage"
    assert normalize_modifier("+29% zu Feuerwiderstand") == "fire_resistance"


def test_near_phrases_do_not_overmatch() -> None:
    assert normalize_modifier("30% reduced Movement Speed") == "unknown"
    assert normalize_modifier("Gain 20 Mana when hit") == "unknown"
