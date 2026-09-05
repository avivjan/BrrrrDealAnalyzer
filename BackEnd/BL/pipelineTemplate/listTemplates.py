from sqlalchemy.orm import Session

from DAL.crud.pipeline_template import get_all_templates
from BL.pipelineTemplate.common.seed import ensure_defaults
from BL.pipelineTemplate.common.mappers import to_res


def list_templates(db: Session):
    ensure_defaults(db)
    rows = get_all_templates(db)
    rows_by_type = {r.deal_type: r for r in rows}
    # Stable order: BRRRR first, then FLIP
    return [to_res(rows_by_type[t]) for t in ("BRRRR", "FLIP") if t in rows_by_type]
