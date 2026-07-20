from pydantic import BaseModel, ConfigDict


class BuildContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    build_id: str
    version: int
    name: str
    author: str
    source_url: str
    source_variant: str
    archetype: str
    core_skills: tuple[str, ...]
    offensive_priorities: tuple[str, ...]
    defensive_priorities: tuple[str, ...]
    item_priorities: tuple[str, ...] = ()
    low_value_stats: tuple[str, ...] = ()
    constraints: tuple[str, ...]


DEFAULT_BUILD_ID = "deadrabb1t-chaos-dot-lich-starter-v2"
V1_BUILD_ID = "deadrabb1t-chaos-dot-lich-starter-v1"

_V1 = BuildContext(
        build_id=V1_BUILD_ID,
        version=1,
        name="ED Contagion Chaos DoT Lich Starter",
        author="DEADRABB1T",
        source_url=(
            "https://mobalytics.gg/poe-2/builds/chaos-dot-lich-starter-deadrabbit"
            "?ws-ngf5-f7d82102-7e77-4a44-ad24-33b67e8ae7bf="
            "activeVariantId%2Cdefault-variant"
        ),
        source_variant="default-variant",
        archetype="Chaos damage over time Lich using Essence Drain and Contagion",
        core_skills=("Essence Drain", "Contagion", "Dark Effigy", "Despair"),
        offensive_priorities=(
            "+ levels to Chaos Spell Skills",
            "Spell Damage and Chaos Damage",
            "Cast Speed is a useful bonus",
        ),
        defensive_priorities=(
            "high Energy Shield",
            "Energy Shield recharge",
            "elemental and chaos resistances",
        ),
        constraints=("The build is mana hungry; account for mana sustain.",),
    )
_BUILDS = {
    V1_BUILD_ID: _V1,
    DEFAULT_BUILD_ID: _V1.model_copy(update={
        "build_id": DEFAULT_BUILD_ID, "version": 2,
        "item_priorities": (
            "+ Level to all Chaos Spell Skills", "+ Level to all Spell Skills", "Spell Damage",
            "Chaos Damage", "Cast Speed", "Energy Shield", "Spirit", "Intelligence",
            "Elemental Resistances", "Chaos Resistance", "Movement Speed on Boots",
            "Mana and Mana Regeneration", "Maximum Life",
        ),
        "low_value_stats": (
            "Attack Damage", "Accuracy", "Bleeding", "Physical Thorns",
            "Elemental Damage without Chaos DoT synergy", "Stun Threshold",
            "Evasion without further synergy",
        ),
    }),
}


def get_builtin_build(build_id: str) -> BuildContext:
    try:
        return _BUILDS[build_id]
    except KeyError as exc:
        raise ValueError("unknown_build") from exc


def list_builtin_builds() -> tuple[BuildContext, ...]:
    return tuple(_BUILDS.values())


# Compatibility aliases for callers that intentionally only use bundled builds.
get_build = get_builtin_build
list_builds = list_builtin_builds
