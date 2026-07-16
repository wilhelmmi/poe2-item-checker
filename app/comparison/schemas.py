from typing import Literal

from pydantic import BaseModel, ConfigDict


class HardCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    status: Literal["pass", "fail", "unknown"]
    message: str
    before: float | None = None
    after: float | None = None
    required: float | None = None


class HardChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_slot: str | None
    checks: list[HardCheck]
