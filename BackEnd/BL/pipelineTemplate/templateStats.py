from sqlalchemy.orm import Session

from DAL.data_models import BoughtBrrrDeal, BoughtFlipDeal
from DAL.crud.pipeline_template import get_template
from ReqRes.common.pipeline_template_schemas import (
    PipelineTemplateStatsRes,
    PipelineStageStat,
    PipelineSubstageStat,
)
from BL.pipelineTemplate.common.pipeline_defaults import default_stages_for


def template_stats(db: Session, deal_type: str) -> PipelineTemplateStatsRes:
    """Return counts so the UI can warn before destructive edits."""
    template = get_template(db, deal_type)
    stages = (template.stages if template else default_stages_for(deal_type)) or []
    known_ids = {s["id"] for s in stages}

    model = BoughtBrrrDeal if deal_type == "BRRRR" else BoughtFlipDeal
    deals = db.query(model.bought_stage, model.completed_substages).all()

    per_stage_deal_count: dict[str, int] = {s["id"]: 0 for s in stages}
    per_substage_completion: dict[str, dict[str, int]] = {
        s["id"]: {sub["id"]: 0 for sub in s.get("subStages", [])} for s in stages
    }
    orphan_stage_deal_count = 0

    for bought_stage, completed_substages in deals:
        if bought_stage in per_stage_deal_count:
            per_stage_deal_count[bought_stage] += 1
        else:
            orphan_stage_deal_count += 1

        if isinstance(completed_substages, dict):
            for sub_id, done in completed_substages.items():
                if not done:
                    continue
                # Count completion against whichever stage currently declares
                # this substage id (if any in the current template).
                for s in stages:
                    if sub_id in per_substage_completion.get(s["id"], {}):
                        per_substage_completion[s["id"]][sub_id] += 1

    stage_stats: list[PipelineStageStat] = []
    for s in stages:
        stage_stats.append(
            PipelineStageStat(
                stageId=s["id"],
                dealCount=per_stage_deal_count.get(s["id"], 0),
                substages=[
                    PipelineSubstageStat(
                        substageId=sub["id"],
                        dealsWithCompletion=per_substage_completion[s["id"]].get(sub["id"], 0),
                    )
                    for sub in s.get("subStages", [])
                ],
            )
        )

    return PipelineTemplateStatsRes(
        dealType=deal_type,
        stages=stage_stats,
        orphanStageDealCount=orphan_stage_deal_count,
    )
