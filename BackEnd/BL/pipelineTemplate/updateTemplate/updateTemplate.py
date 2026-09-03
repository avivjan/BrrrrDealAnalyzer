from sqlalchemy.orm import Session

from ReqRes.common.pipeline_template_schemas import PipelineTemplateUpsert
from DAL.crud.pipeline_template import get_template, insert_template, save_template
from BL.pipelineTemplate.common.mappers import to_res


def update_template(db: Session, deal_type: str, data: PipelineTemplateUpsert):
    row = get_template(db, deal_type)
    stages_json = [s.model_dump() for s in data.stages]
    if row is None:
        row = insert_template(db, deal_type, stages_json)
    else:
        row.stages = stages_json
        row = save_template(db, row)
    return to_res(row)
