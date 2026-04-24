"""CRUD helpers for pipeline templates (one row per deal type)."""

from typing import Literal

from sqlalchemy.orm import Session

from models import PipelineTemplate, BoughtBrrrDeal, BoughtFlipDeal
from pipeline_defaults import default_stages_for
from ReqRes.pipelineTemplate import (
    PipelineTemplateUpsert,
    PipelineTemplateRes,
    PipelineTemplateStatsRes,
    PipelineStageStat,
    PipelineSubstageStat,
)


DealType = Literal["BRRRR", "FLIP"]


def _to_res(row: PipelineTemplate) -> PipelineTemplateRes:
    return PipelineTemplateRes(
        dealType=row.deal_type,  # type: ignore[arg-type]
        stages=row.stages or [],
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def ensure_defaults(db: Session) -> None:
    """Seed default templates for any deal type that does not yet have a row."""
    for deal_type in ("BRRRR", "FLIP"):
        existing = db.query(PipelineTemplate).filter(PipelineTemplate.deal_type == deal_type).first()
        if existing is None:
            db.add(
                PipelineTemplate(
                    deal_type=deal_type,
                    stages=default_stages_for(deal_type),
                )
            )
    db.commit()


def get_template(db: Session, deal_type: DealType) -> PipelineTemplate | None:
    return db.query(PipelineTemplate).filter(PipelineTemplate.deal_type == deal_type).first()


def list_templates(db: Session) -> list[PipelineTemplateRes]:
    ensure_defaults(db)
    rows = db.query(PipelineTemplate).all()
    rows_by_type = {r.deal_type: r for r in rows}
    # Stable order: BRRRR first, then FLIP
    return [_to_res(rows_by_type[t]) for t in ("BRRRR", "FLIP") if t in rows_by_type]


def upsert_template(
    db: Session, deal_type: DealType, data: PipelineTemplateUpsert
) -> PipelineTemplateRes:
    row = get_template(db, deal_type)
    stages_json = [s.model_dump() for s in data.stages]
    if row is None:
        row = PipelineTemplate(deal_type=deal_type, stages=stages_json)
        db.add(row)
    else:
        row.stages = stages_json
    db.commit()
    db.refresh(row)
    return _to_res(row)


def get_stats(db: Session, deal_type: DealType) -> PipelineTemplateStatsRes:
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
