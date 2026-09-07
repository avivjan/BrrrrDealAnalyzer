"""Lightweight probe so the frontend can show a setup banner if env is missing."""

from ReqRes.common.reps_schemas import MIN_DESCRIPTION_LEN
from BL.reps.common import reps_service


def get_config_status() -> dict:
    try:
        cfg = reps_service.get_config()
        # The bucket name and prefix are not returned (F-12): together they
        # are the URL of every evidence object. The UI only needs `configured`.
        return {
            "configured": True,
            "sheet_tab": cfg.sheet_tab,
            "min_description_length": MIN_DESCRIPTION_LEN,
        }
    except reps_service.RepsConfigError as exc:
        return {"configured": False, "detail": str(exc), "min_description_length": MIN_DESCRIPTION_LEN}
