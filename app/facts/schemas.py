from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TradeOutcome = Literal["vendor", "test_1_ex", "price_check", "manual_review"]
CraftingOutcome = Literal["not_candidate", "candidate", "needs_review"]
Confidence = Literal["low", "medium", "high"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModifierFacts(StrictModel):
    source: str
    affix_type: str | None
    name: str | None
    tier: int | None
    tags: list[str]
    raw_text: str
    normalized_key: str
    current_values: list[float]
    roll_ranges: list[list[float]]
    roll_position: float | None = None
    relevance: str | None = None
    config_rule: str | None = None
    crafted: bool
    desecrated: bool
    rune: bool
    implicit: bool
    unique: bool


class ItemFacts(StrictModel):
    item_class: str
    rarity: str
    name: str
    base_type: str | None
    slot_hint: str | None
    item_level: int | None
    required_level: int | None
    required_strength: int | None
    required_dexterity: int | None
    required_intelligence: int | None
    quality: int | None
    sockets: list[str]
    armour: int | None
    armour_augmented: bool
    evasion: int | None
    evasion_augmented: bool
    energy_shield: int | None
    energy_shield_augmented: bool
    spirit: int | None
    granted_skill: str | None
    identified: bool
    corrupted: bool
    known_modifier_count: int
    unknown_modifier_count: int
    modifiers: list[ModifierFacts]
    warnings: list[str]


class Evidence(StrictModel):
    rule_id: str
    message: str
    matched_facts: list[str]


class AssessmentBase(StrictModel):
    confidence: Confidence
    confidence_reasons: list[str]
    evidence: list[Evidence]


class TradeAssessment(AssessmentBase):
    outcome: TradeOutcome


class CraftingAssessment(AssessmentBase):
    outcome: CraftingOutcome


class FactsCheck(StrictModel):
    facts: ItemFacts
    trade: TradeAssessment
    crafting: CraftingAssessment
    warnings: list[str]
    disclaimer: str


class Predicate(StrictModel):
    scope: Literal["item", "modifier"]
    field: Literal[
        "name", "base_type", "rarity", "item_class", "slot_hint",
        "normalized_key", "current_value", "relevance",
    ]
    op: Literal["eq", "gte", "contains"]
    value: str | float
    modifier_key: str | None = None
    modifier_group: str | None = None

    @model_validator(mode="after")
    def validate_language(self) -> "Predicate":
        item_fields = {"name", "base_type", "rarity", "item_class", "slot_hint"}
        modifier_fields = {"normalized_key", "current_value", "relevance"}
        if self.scope == "item" and self.field not in item_fields:
            raise ValueError("Dieses Feld ist für item-Predicates nicht erlaubt.")
        if self.scope == "modifier" and self.field not in modifier_fields:
            raise ValueError("Dieses Feld ist für modifier-Predicates nicht erlaubt.")
        if self.modifier_key is not None and self.scope != "modifier":
            raise ValueError("modifier_key ist nur für modifier-Predicates erlaubt.")
        if self.modifier_group is not None and self.scope != "modifier":
            raise ValueError("modifier_group ist nur für modifier-Predicates erlaubt.")
        if self.field == "current_value" and not (self.modifier_key and self.modifier_group):
            raise ValueError("current_value benötigt modifier_key und modifier_group.")
        if self.op == "gte" and not (
            self.field == "current_value" and isinstance(self.value, (int, float))
        ):
            raise ValueError("gte ist nur für numerische current_value-Predicates erlaubt.")
        if self.op == "contains" and not (
            self.field in {"name", "base_type"} and isinstance(self.value, str)
        ):
            raise ValueError("contains ist nur für textuelle Item-Namen oder Base Types erlaubt.")
        return self


class RuleBase(StrictModel):
    id: str
    priority: int
    source: str = Field(min_length=1)
    confidence: Confidence
    message: str
    predicates: list[Predicate] = Field(min_length=1)


class TradeRule(RuleBase):
    outcome: TradeOutcome


class CraftingRule(RuleBase):
    outcome: CraftingOutcome


class FactsConfig(StrictModel):
    schema_version: Literal[1]
    slot_mapping: dict[str, str]
    modifier_relevance: dict[str, str]
    trade_rules: list[TradeRule]
    crafting_rules: list[CraftingRule]

    @model_validator(mode="after")
    def validate_registry_references(self) -> "FactsConfig":
        from app.parser.normalizations import KNOWN_NORMALIZED_KEYS

        ids = [rule.id for rule in [*self.trade_rules, *self.crafting_rules]]
        if len(ids) != len(set(ids)):
            raise ValueError("Regel-IDs müssen global eindeutig sein.")
        for rules in (self.trade_rules, self.crafting_rules):
            priorities = [rule.priority for rule in rules]
            if len(priorities) != len(set(priorities)):
                raise ValueError("Prioritäten müssen innerhalb eines Assessments eindeutig sein.")
        allowed_slots = {
            "wand", "focus", "helmet", "body_armour", "gloves", "boots",
            "belt", "ring_1", "ring_2", "amulet", "staff",
        }
        if not set(self.slot_mapping.values()) <= allowed_slots:
            raise ValueError("Unbekanntes Slot-Mapping-Ziel.")
        allowed_relevance = {"low", "medium", "high", "defensive"}
        if not set(self.modifier_relevance.values()) <= allowed_relevance:
            raise ValueError("Unbekannter Relevanzwert.")
        if not set(self.modifier_relevance) <= KNOWN_NORMALIZED_KEYS:
            raise ValueError("modifier_relevance referenziert unbekannte Keys.")
        for rule in [*self.trade_rules, *self.crafting_rules]:
            for predicate in rule.predicates:
                if predicate.modifier_key not in (None, *KNOWN_NORMALIZED_KEYS):
                    raise ValueError("Predicate referenziert unbekannten modifier_key.")
                if predicate.field == "normalized_key" and predicate.value not in KNOWN_NORMALIZED_KEYS:
                    raise ValueError("Predicate referenziert unbekannten normalisierten Key.")
                if predicate.field == "slot_hint" and predicate.value not in self.slot_mapping.values():
                    raise ValueError("Predicate referenziert unbekannten Slot-Hinweis.")
        return self
