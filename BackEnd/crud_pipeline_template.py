"""Backwards-compatible shim -- moved to DAL/crud/pipeline_template.py
(persistence) and BL/pipelineTemplate/ (business logic)."""

from DAL.crud.pipeline_template import (  # noqa: F401
    DealType,
    get_template,
    get_all_templates,
    insert_template,
    save_template,
)
from BL.pipelineTemplate.common.seed import ensure_defaults  # noqa: F401
from BL.pipelineTemplate.common.mappers import to_res as _to_res  # noqa: F401
from BL.pipelineTemplate.listTemplates.listTemplates import list_templates  # noqa: F401
from BL.pipelineTemplate.updateTemplate.updateTemplate import update_template as upsert_template  # noqa: F401
from BL.pipelineTemplate.templateStats.templateStats import template_stats as get_stats  # noqa: F401
