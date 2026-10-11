"""POST /arv-estimate (starts a background job) and GET /arv-estimate/{arv_estimate_job_id} (polls it)."""

import logging
import os

from fastapi import APIRouter, HTTPException, Request

from ReqRes.arvEstimate.estimateArv.estimateArvReq import ArvEstimateReq
from ReqRes.arvEstimate.estimateArv.estimateArvJobRes import ArvEstimateJobRes
from BL.arvEstimate.common import arv_estimate_jobs
from BL.arvEstimate.common.anthropic_arv_client import anthropic_api_key
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


@router.post("/arv-estimate", response_model=ArvEstimateJobRes, status_code=202)
def estimate_arv_with_claude_route(payload: ArvEstimateReq, request: Request):
    # Each estimate spends Anthropic API credit and runs live web searches, so
    # every start is audited (never the address or the note) and capped per
    # hour per caller. The estimate itself takes minutes, longer than Netlify's
    # proxy waits, so this only starts a background job; poll the GET below.
    ip = client_ip(request)
    if count_recent("arv_estimate", 60, ip=ip) >= arv_estimates_per_hour_limit():
        audit("arv_estimate", request, detail={"ok": False, "deal_type": payload.deal_type, "reason": "rate_limited"})
        raise HTTPException(status_code=429, detail="Too many ARV estimates in the last hour; try again later.")
    if not anthropic_api_key():
        raise HTTPException(status_code=503, detail="ARV estimate is not configured on the server.")
    job = arv_estimate_jobs.start_arv_estimate_job(payload)
    audit("arv_estimate", request, detail={"ok": True, "deal_type": payload.deal_type, "reason": "started"})
    return job.to_response()


@router.get("/arv-estimate/{arv_estimate_job_id}", response_model=ArvEstimateJobRes)
def get_arv_estimate_job_route(arv_estimate_job_id: str):
    job = arv_estimate_jobs.find_arv_estimate_job(arv_estimate_job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="This ARV estimate is no longer available (the server may have restarted); start a new one.",
        )
    return job.to_response()
