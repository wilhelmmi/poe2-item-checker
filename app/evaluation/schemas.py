import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.facts.schemas import FactsCheck
from app.comparison.schemas import HardChecks
from app.buildfit.schemas import LocalComparison
from app.schemas.management import Slot
from app.schemas.parsing import ParseItemResponse
from app.schemas.parsing import ParseItemRequest


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuildAssessment(StrictModel):
    suitability: Literal[
        "suitable", "conditionally_suitable", "sidegrade_candidate",
        "not_suitable", "unknown_without_profile",
    ]
    reasons: list[str] = Field(min_length=1, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)


class TradeAssessment(StrictModel):
    recommendation: Literal[
        "vendor", "test_1_ex", "price_check", "multiple_exalted",
        "divine_candidate", "manual_review",
    ]
    reasons: list[str] = Field(min_length=1, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)


class CraftingAssessment(StrictModel):
    recommendation: Literal["not_candidate", "candidate", "needs_review"]
    reasons: list[str] = Field(min_length=1, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)


class EvaluationResult(StrictModel):
    build: BuildAssessment
    trade: TradeAssessment
    crafting: CraftingAssessment
    confidence: Literal["low", "medium", "high"]
    confidence_reasons: list[str] = Field(min_length=1, max_length=6)
    warnings: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def reject_unverifiable_generated_claims(self) -> "EvaluationResult":
        prose = [
            *self.build.reasons, *self.build.warnings,
            *self.trade.reasons, *self.trade.warnings,
            *self.crafting.reasons, *self.crafting.warnings,
            *self.confidence_reasons, *self.warnings,
        ]
        text = "\n".join(prose)
        if re.search(r"\b\d+(?:[.,]\d+)?\s*%", text):
            raise ValueError("Numerische Prozentbehauptungen sind in generiertem Text nicht erlaubt.")
        forbidden = [
            r"\b(?:upgrade|downgrade|aufwertung|abwertung|score[ _-]?delta|punktedifferenz)\b",
            r"\b(?:besser|schlechter|stärker|schwächer)\b[^.\n]{0,40}"
            r"\b(?:current|equipped|aktuell(?:e[snmr]?)?|ausgerüstet(?:e[snmr]?)?)\b",
            r"\b(?:current|equipped|aktuell(?:e[snmr]?)?|ausgerüstet(?:e[snmr]?)?)\b"
            r"[^.\n]{0,40}\b(?:besser|schlechter|stärker|schwächer)\b",
            r"\bscore\b[^.\n]{0,24}\b(?:improved|increased|gestiegen|erhöht)\b"
            r"[^.\n]{0,16}\b(?:by\s+)?\d+\s*(?:points?|punkte?)\b",
            r"\bscore\b[^.\n]{0,24}\b\d+\s*(?:points?|punkte?)\b"
            r"[^.\n]{0,16}\b(?:improved|increased|gestiegen|erhöht)\b",
        ]
        if any(re.search(pattern, text, re.I) for pattern in forbidden):
            raise ValueError("Upgrade-/Downgrade- oder Score-Delta-Aussagen sind nicht erlaubt.")
        return self


class ProviderFailure(StrictModel):
    code: str
    message: str


class EvaluateItemRequest(ParseItemRequest):
    target_slot: Slot | None = None
    use_profile: bool = True


class EvaluateItemResponse(StrictModel):
    parse: ParseItemResponse
    local_check: FactsCheck
    evaluation: EvaluationResult | None
    provider: str | None
    model: str | None
    provider_status: Literal["success", "unavailable"]
    provider_error: ProviderFailure | None
    hard_checks: HardChecks
    local_comparison: LocalComparison
    disclaimer: str
