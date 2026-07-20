from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class BuildAnalysis(StrictModel):
    name: ShortText
    author: ShortText
    source_variant: ShortText
    archetype: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    core_skills: list[ShortText] = Field(min_length=1, max_length=20)
    offensive_priorities: list[ShortText] = Field(min_length=1, max_length=20)
    defensive_priorities: list[ShortText] = Field(min_length=1, max_length=20)
    item_priorities: list[ShortText] = Field(min_length=1, max_length=30)
    low_value_stats: list[ShortText] = Field(default_factory=list, max_length=30)
    constraints: list[ShortText] = Field(default_factory=list, max_length=20)
    uncertainties: list[ShortText] = Field(default_factory=list, max_length=20)


class BuildCitation(StrictModel):
    url: HttpUrl
    title: str = Field(min_length=1, max_length=300)


class BuildPreviewRequest(StrictModel):
    source_url: str = Field(min_length=1, max_length=2048)


class BuildPreviewResponse(StrictModel):
    preview_id: str
    source_url: str
    analysis: BuildAnalysis
    citations: list[BuildCitation]
    provider: str
    model: str
    expires_at: str


class ActiveBuild(StrictModel):
    build_id: str | None = Field(default=None, max_length=120)


class DeletedBuild(StrictModel):
    deleted_build_id: str = Field(min_length=1, max_length=120)
    active_build_id: str | None = Field(default=None, max_length=120)
