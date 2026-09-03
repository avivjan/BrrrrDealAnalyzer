"""CRUD helpers for pipeline templates (one row per deal type)."""

from typing import Literal

from sqlalchemy.orm import Session

from DAL.data_models import PipelineTemplate

DealType = Literal["BRRRR", "FLIP"]


def get_template(db: Session, deal_type: DealType) -> PipelineTemplate | None:
    return db.query(PipelineTemplate).filter(PipelineTemplate.deal_type == deal_type).first()


def get_all_templates(db: Session) -> list[PipelineTemplate]:
    return db.query(PipelineTemplate).all()


def insert_template(db: Session, deal_type: DealType, stages: list[dict]) -> PipelineTemplate:
    row = PipelineTemplate(deal_type=deal_type, stages=stages)
    db.add(row)
    return row
