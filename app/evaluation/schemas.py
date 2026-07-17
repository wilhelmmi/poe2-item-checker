import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
        forbidden = (
            r"\b\d+(?:[.,]\d+)?\s*%",
            r"\b(?:score|punkte?differenz|dps[- ]?delta)\b",
            r"\b(?:price|preis|marktwert|trade|verkauf|exalted|divine|currency)\b",
            r"\b(?:craft\w*|gecraft\w*|herstell\w*|recombinat\w*)\b",
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in forbidden):
            raise ValueError("Die API-Antwort enthält eine nicht erlaubte fachliche Aussage.")
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
