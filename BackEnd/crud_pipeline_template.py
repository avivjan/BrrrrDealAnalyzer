"""Backwards-compatible shim -- moved to DAL/crud/pipeline_template.py."""

from DAL.crud.pipeline_template import (  # noqa: F401
    DealType,
    ensure_defaults,
    get_template,
    list_templates,
    upsert_template,
    get_stats,
)
