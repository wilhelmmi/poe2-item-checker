from app.facts.schemas import ItemFacts, ModifierFacts
from app.schemas.items import ParsedItem
from app.facts.config import FACTS_CONFIG


def extract_item_facts(item: ParsedItem) -> ItemFacts:
    config = FACTS_CONFIG
    modifiers: list[ModifierFacts] = []
    for modifier in item.modifiers:
        roll_position = None
        if len(modifier.values) == 1 and len(modifier.roll_ranges) == 1:
            low, high = modifier.roll_ranges[0]
            if high != low:
                roll_position = (modifier.values[0] - low) / (high - low)
        relevance = config.modifier_relevance.get(modifier.normalized_key)
        modifiers.append(ModifierFacts(
            source=modifier.source,
            affix_type=modifier.affix_type,
            name=modifier.name,
            tier=modifier.tier,
            tags=modifier.tags,
            raw_text=modifier.raw_text,
            normalized_key=modifier.normalized_key,
            current_values=modifier.values,
            roll_ranges=modifier.roll_ranges,
            roll_position=roll_position,
            relevance=relevance,
            config_rule=f"modifier_relevance.{modifier.normalized_key}" if relevance else None,
            crafted=modifier.crafted,
            desecrated=modifier.desecrated,
            rune=modifier.rune,
            implicit=modifier.implicit,
            unique=modifier.unique,
        ))
    fact_warnings: list[str] = []
    if any(mod.roll_position is not None and not 0 <= mod.roll_position <= 1 for mod in modifiers):
        fact_warnings.append("roll_position_out_of_range")
    if any(len(mod.roll_ranges) == 1 and mod.roll_ranges[0][0] > mod.roll_ranges[0][1] for mod in modifiers):
        fact_warnings.append("roll_range_reversed")
    return ItemFacts(
        item_class=item.item_class or "",
        rarity=item.rarity or "",
        name=item.name or "",
        base_type=item.base_type,
        slot_hint=config.slot_mapping.get(item.item_class or ""),
        item_level=item.item_level,
        required_level=item.required_level,
        required_strength=item.required_strength,
        required_dexterity=item.required_dexterity,
        required_intelligence=item.required_intelligence,
        quality=item.quality,
        sockets=item.sockets,
        armour=item.armour,
        armour_augmented=item.armour_augmented,
        evasion=item.evasion,
        evasion_augmented=item.evasion_augmented,
        energy_shield=item.energy_shield,
        energy_shield_augmented=item.energy_shield_augmented,
        spirit=item.spirit,
        granted_skill=item.granted_skill,
        identified=item.identified,
        corrupted=item.corrupted,
        known_modifier_count=sum(modifier.normalized_key != "unknown" for modifier in modifiers),
        unknown_modifier_count=sum(
            modifier.normalized_key == "unknown" and modifier.source != "granted_skill"
            for modifier in modifiers
        ),
        modifiers=modifiers,
        warnings=fact_warnings,
    )
