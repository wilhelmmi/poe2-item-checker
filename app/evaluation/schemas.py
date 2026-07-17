import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from app.builds.registry import BuildContext, DEFAULT_BUILD_ID
from app.schemas.management import ProfileData, Slot
from app.schemas.parsing import ParseItemRequest, ParseItemResponse
from app.schemas.items import ParsedItem


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluationResult(StrictModel):
    recommendation: Literal["better", "not_better", "uncertain"]
    confidence: Literal["low", "medium", "high"]
    reasons: list[str] = Field(min_length=1, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def reject_out_of_scope_claims(self) -> "EvaluationResult":
        text = "\n".join([*self.reasons, *self.warnings])
        percent = r"(?:\d+(?:[.,]\d+)?\s*(?:%|percent|prozent)|\w+\s+(?:percent|prozent))"
        relative_performance = (
            percent + r"[^.\n]{0,64}\b(?:dps|than|gegenüber|compared|equipped|ausgerüstet)\b",
            r"\b(?:dps|than|gegenüber|compared|equipped|ausgerüstet)\b[^.\n]{0,64}" + percent,
            percent + r"[^.\n]{0,32}\b(?:stärker|schwächer|besser|schlechter)\b[^.\n]{0,16}\bals\b",
            percent + r"[^.\n]{0,32}\b(?:gain|improvement|performance|leistungsgewinn|steigerung)\b",
            r"\b(?:gain|improvement|performance|leistungsgewinn|steigerung)\b[^.\n]{0,32}" + percent,
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
    equipped: ParsedItem
    target_slot: Slot
    observed_profile: ProfileData | None
    build: BuildContext


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
    equipped: ParsedItem
    evaluation: EvaluationResult | None
    provider: str | None
    model: str | None
    provider_status: Literal["success", "unavailable"]
    provider_error: ProviderFailure | None
    disclaimer: str
