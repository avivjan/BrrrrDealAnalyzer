from DAL.data_models import PipelineTemplate
from ReqRes.common.pipeline_template_schemas import PipelineTemplateRes


def to_res(row: PipelineTemplate) -> PipelineTemplateRes:
    return PipelineTemplateRes(
        dealType=row.deal_type,  # type: ignore[arg-type]
        stages=row.stages or [],
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )
