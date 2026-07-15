from pydantic import BaseModel, ConfigDict, Field


class ModifierData(BaseModel):
    model_config = ConfigDict(frozen=True)
    source: str
    affix_type: str | None = None
    name: str | None = None
    tier: int | None = None
    tags: list[str] = Field(default_factory=list)
    raw_text: str
    normalized_key: str = "unknown"
    values: list[float] = Field(default_factory=list)
    roll_ranges: list[list[float]] = Field(default_factory=list)
    crafted: bool = False
    desecrated: bool = False
    rune: bool = False
    implicit: bool = False
    unique: bool = False


class ParsedItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    raw_text: str
    unknown_lines: list[str] = Field(default_factory=list)
    item_class: str | None = None
    rarity: str | None = None
    name: str | None = None
    base_type: str | None = None
    required_level: int | None = None
    required_strength: int | None = None
    required_dexterity: int | None = None
    required_intelligence: int | None = None
    item_level: int | None = None
    quality: int | None = None
    sockets: list[str] = Field(default_factory=list)
    armour: int | None = None
    armour_augmented: bool = False
    evasion: int | None = None
    evasion_augmented: bool = False
    energy_shield: int | None = None
    energy_shield_augmented: bool = False
    spirit: int | None = None
    granted_skill: str | None = None
    identified: bool = True
    corrupted: bool = False
    modifiers: list[ModifierData] = Field(default_factory=list)
