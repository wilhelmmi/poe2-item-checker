from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.items import ParsedItem
from app.schemas.management import ProfileData, Slot

HistoryStatus = Literal["checked", "equipped", "stored", "listed", "sold", "vendor"]
HistoryCategory = Literal["upgrade", "conditional_upgrade", "sidegrade", "downgrade", "not_suitable", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SaveEvaluationRequest(StrictModel):
    raw_text: str = Field(min_length=1, max_length=50_000)
    target_slot: Slot | None = None
    use_profile: bool = True


class SaleData(StrictModel):
    listed_at: datetime | None = None
    listed_currency: str | None = Field(default=None, max_length=50)
    listed_amount: Decimal | None = Field(default=None, ge=0, decimal_places=4, max_digits=18)
    sold_at: datetime | None = None
    sold_currency: str | None = Field(default=None, max_length=50)
    sold_amount: Decimal | None = Field(default=None, ge=0, decimal_places=4, max_digits=18)
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def validate_sale_pairs(self) -> "SaleData":
        listed = (self.listed_at, self.listed_currency, self.listed_amount)
        sold = (self.sold_at, self.sold_currency, self.sold_amount)
        if any(value is not None for value in listed) and not all(value is not None for value in listed):
            raise ValueError("listed_at, listed_currency and listed_amount must be provided together")
        if any(value is not None for value in sold) and not all(value is not None for value in sold):
            raise ValueError("sold_at, sold_currency and sold_amount must be provided together")
        if self.listed_at and self.listed_at.utcoffset() is None:
            raise ValueError("listed_at must include a timezone")
        if self.sold_at and self.sold_at.utcoffset() is None:
            raise ValueError("sold_at must include a timezone")
        if self.listed_at and self.sold_at and self.sold_at < self.listed_at:
            raise ValueError("sold_at must not be before listed_at")
        return self


class HistoryUpdate(SaleData):
    status: HistoryStatus

    @model_validator(mode="after")
    def require_status_metadata(self) -> "HistoryUpdate":
        if self.status == "listed" and self.listed_amount is None:
            raise ValueError("listed status requires complete listing metadata")
        if self.status == "sold" and self.sold_amount is None:
            raise ValueError("sold status requires complete sale metadata")
        return self


class HistoryEntry(StrictModel):
    id: str
    item_id: str
    parent_evaluation_id: str | None
    target_slot: Slot | None
    status: HistoryStatus
    category: HistoryCategory
    delta_band: str | None
    candidate_score: int
    equipped_score: int | None
    delta: int | None
    confidence: Literal["high", "medium", "low"]
    completeness: Literal["complete", "partial"]
    rule_version: int
    created_at: datetime
    updated_at: datetime
    item: ParsedItem
    sale: SaleData | None
    snapshot: dict


class HistoryPage(StrictModel):
    items: list[HistoryEntry]
    total: int
    limit: int
    offset: int


class BackupItem(StrictModel):
    id: str = Field(min_length=1, max_length=36)
    created_at: datetime
    item: ParsedItem


class BackupEvaluation(StrictModel):
    id: str = Field(min_length=1, max_length=36)
    item_id: str = Field(min_length=1, max_length=36)
    character_id: int
    parent_evaluation_id: str | None
    target_slot: Slot | None
    build_fit_score: int | None
    equipped_item_score: int | None
    score_delta: int | None
    upgrade_recommendation: str | None
    trade_potential_score: int | None
    trade_recommendation: str | None
    confidence: str | None
    completeness: str | None
    rule_version: int | None
    status: HistoryStatus
    local_category: str | None
    local_delta_band: str | None
    snapshot: dict
    reasons: list[str] = Field(max_length=100)
    warnings: list[str] = Field(max_length=100)
    created_at: datetime
    updated_at: datetime


class BackupSale(StrictModel):
    id: str = Field(min_length=1, max_length=36)
    item_id: str = Field(min_length=1, max_length=36)
    listed_at: datetime | None
    listed_currency: str | None
    listed_amount: Decimal | None
    sold_at: datetime | None
    sold_currency: str | None
    sold_amount: Decimal | None
    status: HistoryStatus
    notes: str

    @model_validator(mode="after")
    def validate_metadata(self) -> "BackupSale":
        SaleData.model_validate(self.model_dump(exclude={"id", "item_id", "status"}))
        if self.status == "listed" and self.listed_amount is None:
            raise ValueError("listed status requires complete listing metadata")
        if self.status == "sold" and self.sold_amount is None:
            raise ValueError("sold status requires complete sale metadata")
        return self


class FullBackup(StrictModel):
    schema_version: Literal[1] = 1
    profile: ProfileData
    equipment: dict[Slot, str | None]
    items: list[BackupItem] = Field(max_length=100_000)
    evaluations: list[BackupEvaluation] = Field(max_length=100_000)
    sales: list[BackupSale] = Field(max_length=100_000)

    @field_validator("equipment")
    @classmethod
    def limit_equipment_ids(cls, value: dict[Slot, str | None]) -> dict[Slot, str | None]:
        if any(item_id is not None and (not item_id or len(item_id) > 36) for item_id in value.values()):
            raise ValueError("invalid equipment item id")
        return value

    @model_validator(mode="after")
    def references_are_valid(self) -> "FullBackup":
        item_ids = {item.id for item in self.items}
        evaluation_ids = {evaluation.id for evaluation in self.evaluations}
        sale_ids = {sale.id for sale in self.sales}
        if (len(item_ids) != len(self.items) or len(evaluation_ids) != len(self.evaluations)
                or len(sale_ids) != len(self.sales)):
            raise ValueError("duplicate backup id")
        if set(self.equipment) != {"wand", "focus", "helmet", "body_armour", "gloves", "boots", "belt", "ring_1", "ring_2", "amulet"}:
            raise ValueError("equipment must contain every slot")
        if any(item_id is not None and item_id not in item_ids for item_id in self.equipment.values()):
            raise ValueError("equipment references unknown item")
        if any(e.item_id not in item_ids for e in self.evaluations):
            raise ValueError("evaluation references unknown item")
        if any(e.character_id != 1 for e in self.evaluations):
            raise ValueError("evaluation references unsupported character")
        if any(e.parent_evaluation_id and e.parent_evaluation_id not in evaluation_ids for e in self.evaluations):
            raise ValueError("evaluation references unknown parent")
        if any(e.parent_evaluation_id == e.id for e in self.evaluations):
            raise ValueError("evaluation cannot reference itself")
        if any(s.item_id not in item_ids for s in self.sales):
            raise ValueError("sale references unknown item")
        if len({sale.item_id for sale in self.sales}) != len(self.sales):
            raise ValueError("only one sale record per item is supported")
        parents = {evaluation.id: evaluation.parent_evaluation_id for evaluation in self.evaluations}
        for evaluation_id in parents:
            seen: set[str] = set()
            current: str | None = evaluation_id
            while current is not None:
                if current in seen:
                    raise ValueError("evaluation lineage must be acyclic")
                seen.add(current)
                current = parents.get(current)
        return self
