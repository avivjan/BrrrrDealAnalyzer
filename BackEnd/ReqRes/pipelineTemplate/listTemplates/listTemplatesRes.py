"""Re-exported from ReqRes.common.pipeline_template_schemas -- the schema is defined there, once, for the whole app."""

from ReqRes.common.pipeline_template_schemas import PipelineTemplateRes  # noqa: F401

from typing import List

ListTemplatesRes = List[PipelineTemplateRes]
