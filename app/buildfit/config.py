from pathlib import Path
from typing import Literal

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.parser.normalizations import KNOWN_NORMALIZED_KEYS
from app.schemas.management import SLOTS


class BuildFitConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    base_score: int = Field(ge=0, le=100)
    modifier_weights: dict[str, int]
    slot_multipliers: dict[str, dict[str, float]]
    defence_caps: dict[Literal["energy_shield", "life"], int]

    @model_validator(mode="after")
    def validate_semantics(self) -> "BuildFitConfig":
        if set(self.defence_caps) != {"energy_shield", "life"}:
            raise ValueError("defence_caps muss exakt energy_shield und life enthalten.")
        if not self.modifier_weights:
            raise ValueError("modifier_weights darf nicht leer sein.")
        if not set(self.modifier_weights) <= KNOWN_NORMALIZED_KEYS:
            raise ValueError("modifier_weights enthält unbekannte Modifierkeys.")
        if any(not -30 <= weight <= 30 for weight in self.modifier_weights.values()):
            raise ValueError("Modifiergewichte müssen zwischen -30 und 30 liegen.")
        if not set(self.slot_multipliers) <= set(SLOTS):
            raise ValueError("slot_multipliers enthält unbekannte Slots.")
        for multipliers in self.slot_multipliers.values():
            if not set(multipliers) <= set(self.modifier_weights):
                raise ValueError("Slot-Multiplikator referenziert unbekannten Modifierkey.")
            if any(not math.isfinite(value) or not 0.5 <= value <= 2 for value in multipliers.values()):
                raise ValueError("Slot-Multiplikatoren müssen endlich und zwischen 0.5 und 2 sein.")
        if any(not 0 <= value <= 30 for value in self.defence_caps.values()):
            raise ValueError("Defence-Caps müssen zwischen 0 und 30 liegen.")
        return self


BUILD_FIT_CONFIG = BuildFitConfig.model_validate_json(
    (Path(__file__).parents[1] / "rules" / "build-fit-v1.json").read_text(encoding="utf-8")
)
