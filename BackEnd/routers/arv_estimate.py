"""POST /arv-estimate."""

import logging
import os

from fastapi import APIRouter, HTTPException, Request

from ReqRes.arvEstimate.estimateArv.estimateArvReq import ArvEstimateReq
from ReqRes.arvEstimate.estimateArv.estimateArvRes import ArvEstimateRes
from BL.arvEstimate import estimateArv
from BL.arvEstimate.common.anthropic_arv_client import ArvEstimateFailedError, ArvEstimateNotConfiguredError
from BL.auth.common.audit import client_ip, count_recent, record as audit

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_ARV_ESTIMATES_PER_HOUR = 20


def arv_estimates_per_hour_limit() -> int:
    raw = (os.getenv("ARV_ESTIMATE_PER_HOUR") or "").strip()
    try:
        return int(raw) if raw else DEFAULT_ARV_ESTIMATES_PER_HOUR
    except ValueError:
        return DEFAULT_ARV_ESTIMATES_PER_HOUR


@router.post("/arv-estimate", response_model=ArvEstimateRes)
def estimate_arv_with_claude_route(payload: ArvEstimateReq, request: Request):
    # Each estimate spends Anthropic API credit and runs live web searches, so
    # every attempt is audited (never the address or the note) and capped per
    # hour per caller.
    ip = client_ip(request)
    if count_recent("arv_estimate", 60, ip=ip) >= arv_estimates_per_hour_limit():
        audit("arv_estimate", request, detail={"ok": False, "deal_type": payload.deal_type, "reason": "rate_limited"})
        raise HTTPException(status_code=429, detail="Too many ARV estimates in the last hour; try again later.")
    try:
        arv_estimate = estimateArv.estimate_arv_with_claude(payload)
    except ArvEstimateNotConfiguredError:
        raise HTTPException(status_code=503, detail="ARV estimate is not configured on the server.")
    except ArvEstimateFailedError as error:
        audit("arv_estimate", request, detail={"ok": False, "deal_type": payload.deal_type, "reason": "failed"})
        raise HTTPException(status_code=502, detail=str(error))
    audit("arv_estimate", request, detail={"ok": True, "deal_type": payload.deal_type})
    return arv_estimate
