from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

EquipmentSlotName = Literal[
    "wand",
    "focus",
    "helmet",
    "body_armour",
    "gloves",
    "boots",
    "belt",
    "ring_1",
    "ring_2",
    "amulet",
]
ModifierSource = Literal[
    "implicit",
    "explicit",
    "crafted",
    "desecrated",
    "rune",
    "unique",
    "granted_skill",
]


class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CharacterProfile(OrmSchema):
    id: int | None = None
    name: str
    build_stage: str = "early_endgame"
    life: int | None = None
    energy_shield: int | None = None
    mana: int | None = None
    spirit: int | None = None
    strength: int | None = None
    dexterity: int | None = None
    intelligence: int | None = None
    fire_resistance: int | None = None
    cold_resistance: int | None = None
    lightning_resistance: int | None = None
    chaos_resistance: int | None = None
    resistance_cap: int = 75
    notes: str = ""


class Modifier(OrmSchema):
    id: int | None = None
    item_id: UUID | None = None
    source: ModifierSource
    affix_type: Literal["prefix", "suffix"] | None = None
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


class Item(OrmSchema):
    id: UUID = Field(default_factory=uuid4)
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modifiers: list[Modifier] = Field(default_factory=list)


class EquipmentSlot(OrmSchema):
    character_id: int
    slot: EquipmentSlotName
    item_id: UUID


class Evaluation(OrmSchema):
    id: UUID = Field(default_factory=uuid4)
    item_id: UUID
    character_id: int
    target_slot: EquipmentSlotName | None = None
    build_fit_score: int | None = Field(default=None, ge=0, le=100)
    equipped_item_score: int | None = Field(default=None, ge=0, le=100)
    score_delta: int | None = None
    upgrade_recommendation: str | None = None
    trade_potential_score: int | None = Field(default=None, ge=0, le=100)
    trade_recommendation: str | None = None
    confidence: str | None = None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SaleRecord(OrmSchema):
    id: UUID = Field(default_factory=uuid4)
    item_id: UUID
    listed_at: datetime | None = None
    listed_currency: str | None = None
    listed_amount: Decimal | None = None
    sold_at: datetime | None = None
    sold_currency: str | None = None
    sold_amount: Decimal | None = None
    status: str = "listed"
    notes: str = ""
