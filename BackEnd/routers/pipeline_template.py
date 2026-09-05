"""/pipeline-templates -- bought-deal stages/substages."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from ReqRes.common.pipeline_template_schemas import (
    PipelineTemplateUpsert,
    PipelineTemplateRes,
    PipelineTemplateStatsRes,
)
from BL.pipelineTemplate.listTemplates import list_templates as list_templates_bl
from BL.pipelineTemplate.updateTemplate import update_template as update_template_bl
from BL.pipelineTemplate.templateStats import template_stats as template_stats_bl

router = APIRouter()

_VALID_DEAL_TYPES = {"BRRRR", "FLIP"}


def _require_valid_deal_type(deal_type: str) -> str:
    if deal_type not in _VALID_DEAL_TYPES:
        raise HTTPException(status_code=400, detail="deal_type must be 'BRRRR' or 'FLIP'")
    return deal_type


@router.get("/pipeline-templates", response_model=List[PipelineTemplateRes])
def list_pipeline_templates_route(db: Session = Depends(get_db)):
    return list_templates_bl(db)


@router.put("/pipeline-templates/{deal_type}", response_model=PipelineTemplateRes)
def update_pipeline_template_route(
    deal_type: str,
    payload: PipelineTemplateUpsert,
    db: Session = Depends(get_db),
):
    _require_valid_deal_type(deal_type)
    return update_template_bl(db, deal_type, payload)  # type: ignore[arg-type]


@router.get("/pipeline-templates/{deal_type}/stats", response_model=PipelineTemplateStatsRes)
def pipeline_template_stats_route(deal_type: str, db: Session = Depends(get_db)):
    _require_valid_deal_type(deal_type)
    return template_stats_bl(db, deal_type)  # type: ignore[arg-type]
