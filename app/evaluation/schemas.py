import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError

from app.builds.registry import BuildContext, DEFAULT_BUILD_ID
from app.schemas.management import ProfileData, Slot
from app.schemas.parsing import ParseItemRequest, ParseItemResponse
from app.schemas.items import ParsedItem


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuildImpacts(StrictModel):
    damage: Literal["better", "similar", "worse"]
    defensive: Literal["better", "similar", "worse"]
    resistances: Literal["better", "similar", "worse"]
    utility: Literal["better", "similar", "worse"]


BoundedExplanation = Annotated[str, StringConstraints(min_length=1, max_length=500)]


class EvaluationResult(StrictModel):
    recommendation: Literal["better", "not_better", "uncertain"]
    confidence: Literal["low", "medium", "high"]
    reasons: list[BoundedExplanation] = Field(min_length=1, max_length=8)
    warnings: list[BoundedExplanation] = Field(default_factory=list, max_length=8)
    verdict: Literal["upgrade", "sidegrade", "downgrade"]
    current_item_name: str = Field(min_length=1, max_length=200)
    new_item_name: str = Field(min_length=1, max_length=200)
    gains: list[BoundedExplanation] = Field(default_factory=list, max_length=8)
    losses: list[BoundedExplanation] = Field(default_factory=list, max_length=8)
    impacts: BuildImpacts
    clear_recommendation: str = Field(min_length=1, max_length=500)
    recommended_target_slot: Slot | None = None

    @model_validator(mode="after")
    def reject_out_of_scope_claims(self) -> "EvaluationResult":
        expected = {"better": "upgrade", "not_better": "downgrade", "uncertain": "sidegrade"}
        if self.verdict != expected[self.recommendation]:
            raise ValueError("verdict must match recommendation")
        text = "\n".join([*self.reasons, *self.warnings, *self.gains, *self.losses, self.clear_recommendation])
        percent = r"(?:\d+(?:[.,]\d+)?\s*(?:%|percent|prozent)|\w+\s+(?:percent|prozent))"
        relative_performance = (
            percent + r"[^.\n]{0,32}\b(?:dps|damage output|gesamt(?:schaden|leistung))\b",
            r"\b(?:dps|damage output|gesamt(?:schaden|leistung))\b[^.\n]{0,32}" + percent,
            percent + r"[^.\n]{0,32}\b(?:stärker|schwächer|besser|schlechter)\b[^.\n]{0,16}\bals\b",
            percent + r"[^.\n]{0,32}\b(?:stronger|weaker|better|worse)\b[^.\n]{0,16}\bthan\b",
            percent + r"[^.\n]{0,16}\b(?:more|less)\s+(?:damage|dps)\b[^.\n]{0,16}\bthan\b",
            percent + r"[^.\n]{0,16}\b(?:mehr|weniger)\s+(?:schaden|dps)\b[^.\n]{0,16}\bals\b",
            percent + r"[^.\n]{0,24}\b(?:performance|leistungsgewinn|leistungssteigerung)\b",
            r"\b(?:performance|leistungsgewinn|leistungssteigerung)\b[^.\n]{0,24}" + percent,
            r"\b(?:gain|improvement|steigerung)\s+(?:is|of|by|beträgt)\s+" + percent,
            r"\b(?:score|punkte?differenz|dps[- ]?delta)\b",
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in relative_performance):
            raise PydanticCustomError(
                "evaluation_claim_relative_performance",
                "Relative Leistungsbehauptungen sind nicht erlaubt.",
            )
        market_claim = (
            r"\b(?:price|preis|market\s+value|marktwert|handelswert|verkaufswert|worth|wertvoll|"
            r"sale|sell|vendor|verkauf\w*|buy|kauf\w*|listing|exalted|divine|currency)\b",
            r"\b(?:trade|trading|handel)\b(?![- ]?offs?\b)",
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in market_claim):
            raise PydanticCustomError(
                "evaluation_claim_market_value", "Marktwertaussagen sind nicht erlaubt."
            )
        crafted_action = (
            r"\b(?:add|use|remove)\s+(?:an?\s+|the\s+)?crafted\s+(?:modifier|mod)\b|"
            r"\bcrafted\s+(?:modifier|mod)\b[^.\n]{0,48}\b(?:should|add|use|remove|replace)\b"
        )
        if re.search(crafted_action, text, re.IGNORECASE):
            raise PydanticCustomError(
                "evaluation_claim_crafting_action",
                "Crafting-Handlungen oder -Empfehlungen sind nicht erlaubt.",
            )
        crafting_text = re.sub(
            r"\b(?:has|contains)\s+(?:a\s+)?crafted\s+(?:modifier|mod)\b|"
            r"\b(?:suffix|prefix|modifier|mod)\s+is\s+crafted\b|"
            r"\bder\s+gecraftete\s+(?:modifier|mod)\b",
            "observed_modifier",
            text,
            flags=re.IGNORECASE,
        )
        if re.search(
            r"\b(?:craft\w*|gecraft\w*|herstell\w*|recombinat\w*|reroll\w*|"
            r"use\s+an?\s+essence|apply\s+an?\s+omen|slam\w*|annul\w*|"
            r"add\s+an?\s+(?:prefix|suffix)|socket\s+an?\s+rune)\b",
            crafting_text,
            re.IGNORECASE,
        ):
            raise PydanticCustomError(
                "evaluation_claim_crafting_action",
                "Crafting-Handlungen oder -Empfehlungen sind nicht erlaubt.",
            )
        return self


class EvaluationInput(StrictModel):
    candidate: ParsedItem
    equipped: ParsedItem | None
    equipped_slots: dict[Slot, ParsedItem | None] = Field(default_factory=dict)
    target_slot: Slot
    target_slots: list[Slot] = Field(default_factory=list)
    comparison_slots: list[Slot] = Field(default_factory=list)
    available_target_slots: list[Slot] = Field(default_factory=list)
    observed_profile: ProfileData | None
    build: BuildContext

    @model_validator(mode="after")
    def populate_single_slot_compatibility_fields(self) -> "EvaluationInput":
        if not self.target_slots:
            self.target_slots = [self.target_slot]
        if not self.equipped_slots:
            self.equipped_slots = {self.target_slot: self.equipped}
        if not self.comparison_slots:
            self.comparison_slots = list(self.target_slots)
        if not self.available_target_slots:
            self.available_target_slots = list(self.comparison_slots)
        if self.target_slot not in self.target_slots or len(set(self.target_slots)) != len(self.target_slots):
            raise ValueError("target_slots must uniquely contain target_slot")
        if len(set(self.comparison_slots)) != len(self.comparison_slots):
            raise ValueError("comparison_slots must be unique")
        if set(self.equipped_slots) != set(self.comparison_slots):
            raise ValueError("equipped_slots must exactly match target_slots/comparison_slots")
        if not set(self.available_target_slots) <= set(self.comparison_slots):
            raise ValueError("available_target_slots must be contained in comparison_slots")
        alias = self.equipped_slots[self.target_slot]
        if alias is None and len(self.target_slots) > 1:
            alias = next((item for item in self.equipped_slots.values() if item is not None), None)
        if alias != self.equipped:
            raise ValueError("equipped must match the canonical equipped_slots item")
        return self


class ProviderFailure(StrictModel):
    code: str
    message: str


class EvaluateItemRequest(ParseItemRequest):
    target_slot: Slot
    build_id: str = DEFAULT_BUILD_ID
    use_profile: bool = True


class EvaluateItemResponse(StrictModel):
    parse: ParseItemResponse
    build: BuildContext
    target_slot: Slot
    equipped: ParsedItem | None
    equipped_slots: dict[Slot, ParsedItem | None]
    target_slots: list[Slot]
    comparison_slots: list[Slot] = Field(default_factory=list)
    available_target_slots: list[Slot] = Field(default_factory=list)
    evaluation: EvaluationResult | None
    provider: str | None
    model: str | None
    provider_status: Literal["success", "unavailable"]
    provider_error: ProviderFailure | None
    disclaimer: str
