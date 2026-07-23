"""Locale aliases used at the parser boundary.

The rest of the application deliberately continues to use the English values from
the original item export format.
"""

import re

ITEM_CLASS_ALIASES = {
    "Zauberstäbe": "Wands",
    "Fokusse": "Foci",
    "Helme": "Helmets",
    "Körperrüstungen": "Body Armours",
    "Handschuhe": "Gloves",
    "Stiefel": "Boots",
    "Gürtel": "Belts",
    "Ringe": "Rings",
    "Amulette": "Amulets",
    "Stäbe": "Staves",
    "Talismane": "Charms",
    "Charms": "Charms",
}

RARITY_ALIASES = {
    "Normal": "Normal",
    "Magisch": "Magic",
    "Selten": "Rare",
    "Einzigartig": "Unique",
}

GERMAN_ITEM_MARKERS = re.compile(
    r"(?im)^(?:Gegenstandsklasse|Seltenheit|Anforderungen|Gegenstandsstufe|Qualität|"
    r"Rüstung|Ausweichwert|Energieschild|Willenskraft|Nicht identifiziert|Verderbt)\s*:"
    r"|^(?:Nicht identifiziert|Verderbt)$"
)


def canonical_item_class(value: str) -> str:
    return ITEM_CLASS_ALIASES.get(value, value)


def canonical_rarity(value: str) -> str:
    return RARITY_ALIASES.get(value, value)


def is_german_item_text(raw_text: str) -> bool:
    """Detect the item locale from stable export headers, not modifier vocabulary."""
    return bool(GERMAN_ITEM_MARKERS.search(raw_text))
