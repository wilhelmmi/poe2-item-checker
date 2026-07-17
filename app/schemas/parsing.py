from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.items import ParsedItem

ParseWarningCode = Literal[
    "input_missing_line_breaks",
    "unknown_lines_preserved",
    "missing_item_identity",
    "no_modifiers_detected",
    "assessment_skipped",
]
LineBreakCode = Literal[
    "before_separator",
    "after_separator",
    "before_rarity",
    "after_rarity",
    "between_rare_name_base",
    "before_modifier_header",
    "after_modifier_header",
]


class ParseItemRequest(BaseModel):
    raw_text: str

    @field_validator("raw_text")
    @classmethod
    def reject_blank_input(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Itemtext darf nicht leer sein.")
        return value


class ParseWarning(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: ParseWarningCode
    message: str
    lines: list[int]
    raw_lines: list[str]


class LineBreakInsertion(BaseModel):
    model_config = ConfigDict(frozen=True)
    offset: int = Field(
        description="Nullbasierter Einfügeoffset relativ zum unveränderten Originaltext."
    )
    code: LineBreakCode
    message: str


class LineBreakSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True)
    suggested_text: str
    insertions: list[LineBreakInsertion]


class ParseItemResponse(BaseModel):
    item: ParsedItem
    warnings: list[ParseWarning]
    line_break_suggestion: LineBreakSuggestion | None = None
    auto_format_status: Literal["unchanged", "safe", "ambiguous"] = "unchanged"
