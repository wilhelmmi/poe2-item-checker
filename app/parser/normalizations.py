import re

NORMALIZATION_REGISTRY_VERSION = 1
NORMALIZATION_PATTERNS = (
    (re.compile(r"increased Spell Damage", re.I), "increased_spell_damage"),
    (re.compile(r"Level of all Chaos Spell Skills", re.I), "all_chaos_spell_skill_levels"),
    (re.compile(r"Level of all Spell Skills", re.I), "all_spell_skill_levels"),
    (re.compile(r"increased Chaos Damage", re.I), "increased_chaos_damage"),
    (re.compile(r"increased Cast Speed", re.I), "increased_cast_speed"),
    (re.compile(r"Gain .+ of Damage as Extra Lightning Damage", re.I), "extra_lightning_damage"),
    (re.compile(r"Mana per enemy killed", re.I), "mana_per_enemy_killed"),
    (re.compile(r"increased Movement Speed", re.I), "movement_speed"),
    (re.compile(r"to Fire Resistance", re.I), "fire_resistance"),
    (re.compile(r"to Cold Resistance", re.I), "cold_resistance"),
    (re.compile(r"to Lightning Resistance", re.I), "lightning_resistance"),
    (re.compile(r"to Chaos Resistance", re.I), "chaos_resistance"),
    (re.compile(r"to maximum Energy Shield", re.I), "maximum_energy_shield"),
    (re.compile(r"to maximum Life", re.I), "maximum_life"),
    (re.compile(r"Life Regeneration per second", re.I), "life_regeneration"),
    (re.compile(r"to Spirit", re.I), "spirit"),
    (re.compile(r"to Stun Threshold", re.I), "stun_threshold"),
    (re.compile(r"increased Lightning Damage", re.I), "increased_lightning_damage"),
    (re.compile(r"increased Mana Regeneration Rate", re.I), "mana_regeneration"),
)
KNOWN_NORMALIZED_KEYS = frozenset(key for _, key in NORMALIZATION_PATTERNS)


def normalize_modifier(raw_text: str) -> str:
    return next(
        (key for pattern, key in NORMALIZATION_PATTERNS if pattern.search(raw_text)),
        "unknown",
    )
