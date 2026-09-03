from sqlalchemy.orm import Session

from DAL.crud.pipeline_template import get_template
from pipeline_defaults import default_stages_for


def first_stage_id(db: Session, deal_type: str) -> str:
    """Return the ID of the first stage in the current pipeline template."""
    row = get_template(db, deal_type)
    stages = (row.stages if row and row.stages else default_stages_for(deal_type)) or []
    if stages:
        return stages[0]["id"]
    return "purchase"
