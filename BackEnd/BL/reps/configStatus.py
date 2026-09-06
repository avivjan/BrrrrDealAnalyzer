"""Lightweight probe so the frontend can show a setup banner if env is missing."""

from ReqRes.common.reps_schemas import MIN_DESCRIPTION_LEN
from BL.reps.common import reps_service


def get_config_status() -> dict:
    try:
        cfg = reps_service.get_config()
        return {
            "configured": True,
            "sheet_tab": cfg.sheet_tab,
            "bucket_name": cfg.bucket_name,
            "base_prefix": cfg.base_prefix,
            "min_description_length": MIN_DESCRIPTION_LEN,
        }
    except reps_service.RepsConfigError as exc:
        return {"configured": False, "detail": str(exc), "min_description_length": MIN_DESCRIPTION_LEN}
