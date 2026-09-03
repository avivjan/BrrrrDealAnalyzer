from sqlalchemy.orm import Session

from DAL.data_models import PipelineTemplate
from DAL.crud.pipeline_template import get_template
from BL.pipelineTemplate.common.pipeline_defaults import default_stages_for


def ensure_defaults(db: Session) -> None:
    """Seed default templates for any deal type that does not yet have a row."""
    for deal_type in ("BRRRR", "FLIP"):
        existing = get_template(db, deal_type)
        if existing is None:
            db.add(
                PipelineTemplate(
                    deal_type=deal_type,
                    stages=default_stages_for(deal_type),
                )
            )
    db.commit()
