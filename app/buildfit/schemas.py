from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.comparison.schemas import HardChecks
from app.schemas.management import Slot

Category = Literal["upgrade", "conditional_upgrade", "sidegrade", "downgrade", "not_suitable", "unknown"]
DeltaBand = Literal["major_upgrade", "positive", "sidegrade", "negative", "major_downgrade"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str
    points: int
    message: str
    value: float | None = None
    cap: float | None = None


class ScoredItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: int
    evidence: list[Evidence]
    unknown_modifier_count: int
    completeness: Literal["complete", "partial"]
    warnings: list[str]
    confidence: Literal["high", "medium", "low"]
    known_relevant_modifier_count: int
    rule_version: int


class EvidenceGroups(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_winners: list[Evidence]
    candidate_losers: list[Evidence]
    equipped_winners: list[Evidence]
    equipped_losers: list[Evidence]


class SlotComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_slot: Slot
    candidate: ScoredItem
    equipped: ScoredItem | None
    delta: int | None
    delta_band: DeltaBand | None
    category: Category
    hard_checks: HardChecks
    warnings: list[str]
    evidence_groups: EvidenceGroups


class LocalComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparisons: list[SlotComparison]
    recommended_target: Slot | None
