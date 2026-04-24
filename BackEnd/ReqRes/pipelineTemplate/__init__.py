from typing import List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class PipelineSubStage(BaseModel):
    """Sub-stage inside a bought-deal pipeline stage.

    `id` is a stable identifier (slug for defaults, `sub_<uuid>` for user-added
    entries). Renames / reorders never mutate `id` so existing deals keep
    referencing the same substages in `completed_substages`.
    """

    id: str = Field(..., min_length=1, max_length=128)
    label: str = Field(..., min_length=1, max_length=200)

    @field_validator("id")
    @classmethod
    def _strip_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("id cannot be blank")
        return v

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label cannot be blank")
        return v


class PipelineStage(BaseModel):
    """Stage in a bought-deal pipeline template."""

    id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=200)
    subStages: List[PipelineSubStage] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _strip_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("id cannot be blank")
        return v

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be blank")
        return v

    @model_validator(mode="after")
    def _validate_unique_substage_ids(self) -> "PipelineStage":
        seen: set[str] = set()
        for sub in self.subStages:
            if sub.id in seen:
                raise ValueError(
                    f"Duplicate substage id '{sub.id}' within stage '{self.id}'"
                )
            seen.add(sub.id)
        return self


class PipelineTemplateUpsert(BaseModel):
    """Payload for PUT /pipeline-templates/{deal_type}."""

    stages: List[PipelineStage] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_unique_stage_ids(self) -> "PipelineTemplateUpsert":
        seen: set[str] = set()
        for stage in self.stages:
            if stage.id in seen:
                raise ValueError(f"Duplicate stage id '{stage.id}' in pipeline")
            seen.add(stage.id)
        return self


class PipelineTemplateRes(BaseModel):
    """Response shape for a single pipeline template row."""

    dealType: Literal["BRRRR", "FLIP"]
    stages: List[PipelineStage]
    updated_at: str | None = None


class PipelineSubstageStat(BaseModel):
    substageId: str
    dealsWithCompletion: int


class PipelineStageStat(BaseModel):
    stageId: str
    dealCount: int
    substages: List[PipelineSubstageStat] = Field(default_factory=list)


class PipelineTemplateStatsRes(BaseModel):
    dealType: Literal["BRRRR", "FLIP"]
    stages: List[PipelineStageStat]
    orphanStageDealCount: int = 0
