"""The `/arv-estimate` orchestrator: ask Claude for the ARV of one property.

Nothing is persisted; the estimate goes straight back to the popup. The
try/except -> HTTPException translation is an HTTP concern and stays in the
router.
"""

from BL.arvEstimate.common.anthropic_arv_client import request_arv_estimate_from_claude
from ReqRes.common.arv_estimate_schemas import ArvEstimateReq, ArvEstimateRes


def estimate_arv_with_claude(arv_estimate_request: ArvEstimateReq) -> ArvEstimateRes:
    return request_arv_estimate_from_claude(arv_estimate_request)
