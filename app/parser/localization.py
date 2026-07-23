"""Locale aliases used at the parser boundary.

The rest of the application deliberately continues to use the English values from
the original item export format.
"""

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


def canonical_item_class(value: str) -> str:
    return ITEM_CLASS_ALIASES.get(value, value)


def canonical_rarity(value: str) -> str:
    return RARITY_ALIASES.get(value, value)
