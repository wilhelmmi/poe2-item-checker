from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.items import ParsedItem

Slot = Literal["wand", "focus", "helmet", "body_armour", "gloves", "boots", "belt", "ring_1", "ring_2", "amulet", "charm_1", "charm_2", "charm_3"]
SLOTS: tuple[Slot, ...] = ("wand", "focus", "helmet", "body_armour", "gloves", "boots", "belt", "ring_1", "ring_2", "amulet", "charm_1", "charm_2", "charm_3")
LEGACY_SLOTS = SLOTS[:-3]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileData(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    build_stage: str = Field(default="early_endgame", min_length=1, max_length=50)
    character_level: int | None = Field(default=None, ge=1, le=100)
    life: int | None = Field(default=None, ge=0)
    energy_shield: int | None = Field(default=None, ge=0)
    mana: int | None = Field(default=None, ge=0)
    spirit: int | None = Field(default=None, ge=0)
    spirit_required: int | None = Field(default=None, ge=0)
    spirit_reserved: int | None = Field(default=None, ge=0)
    strength: int | None = Field(default=None, ge=0)
    dexterity: int | None = Field(default=None, ge=0)
    intelligence: int | None = Field(default=None, ge=0)
    fire_resistance: int | None = None
    cold_resistance: int | None = None
    lightning_resistance: int | None = None
    chaos_resistance: int | None = None
    resistance_cap: int = Field(default=75, ge=0, le=100)
    notes: str = Field(default="", max_length=4000)


class EquipmentItem(StrictModel):
    id: str
    item: ParsedItem


class EquipmentResponse(StrictModel):
    slots: dict[Slot, EquipmentItem | None]
    charm_capacity: int = Field(default=1, ge=1, le=3)
    available_charm_slots: list[Slot] = Field(default_factory=lambda: ["charm_1"])


class EquipmentPut(StrictModel):
    raw_text: str = Field(min_length=1, max_length=50_000)


class EquipmentEquip(StrictModel):
    """Equip an item according to its item class, including two-handed loadouts."""

    raw_text: str = Field(min_length=1, max_length=50_000)
    ring_slot: Literal["ring_1", "ring_2"] = "ring_1"
    target_slot: Slot | None = None


class SeedProfile(StrictModel):
    name: str
    build_stage: str
    language: Literal["de"]
    game_terms_language: Literal["en"]
    trade_preference: Literal["test_items_from_1_exalted"]
    character_sheet: "SeedSheet"


class SeedSheet(StrictModel):
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


class EquipmentImport(StrictModel):
    schema_version: Literal[1]
    profile: SeedProfile
    equipment_raw_text: dict[Slot, str]


class EquipmentExport(StrictModel):
    schema_version: Literal[2, 3] = 3
    profile: ProfileData
    equipment_raw_text: dict[Slot, str | None]

    @model_validator(mode="after")
    def require_complete_slot_snapshot(self) -> "EquipmentExport":
        expected = LEGACY_SLOTS if self.schema_version == 2 else SLOTS
        if set(self.equipment_raw_text) != set(expected):
            raise ValueError("equipment_raw_text must contain all slots for its schema version")
        return self


class StructuredEquipmentItem(StrictModel):
    item_class: str = Field(min_length=1, max_length=100)
    rarity: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=200)
    base: str = Field(min_length=1, max_length=200)
    item_level: int | None = Field(default=None, ge=1, le=100)
    energy_shield: int | None = Field(default=None, ge=0)
    mods: list[str] = Field(min_length=1, max_length=100)


class StructuredCharm(StrictModel):
    rarity: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=200)
    base: str = Field(min_length=1, max_length=200)


class StructuredEquipmentImport(StrictModel):
    """Explicit schema for structured equipment snapshots without a schema version."""

    wand: StructuredEquipmentItem
    focus: StructuredEquipmentItem
    helmet: StructuredEquipmentItem
    body_armour: StructuredEquipmentItem
    gloves: StructuredEquipmentItem
    boots: StructuredEquipmentItem
    belt: StructuredEquipmentItem
    ring1: StructuredEquipmentItem
    ring2: StructuredEquipmentItem
    amulet: StructuredEquipmentItem
    charms: list[StructuredCharm] = Field(default_factory=list, max_length=3)


EquipmentImportData = EquipmentImport | EquipmentExport | StructuredEquipmentImport
