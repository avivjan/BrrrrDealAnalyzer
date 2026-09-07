"""POST /send-offer."""

import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Request

from ReqRes.email.sendOffer.sendOfferReq import SendOfferReq
from ReqRes.email.sendOffer.sendOfferRes import SendOfferRes
from BL.email.sendOffer import send_offer_email
from BL.auth.common.audit import client_ip, count_recent, record as audit

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_SEND_OFFER_PER_HOUR = 30


def send_offer_limit() -> int:
    raw = (os.getenv("SEND_OFFER_PER_HOUR") or "").strip()
    try:
        return int(raw) if raw else DEFAULT_SEND_OFFER_PER_HOUR
    except ValueError:
        return DEFAULT_SEND_OFFER_PER_HOUR


@router.post("/send-offer", response_model=SendOfferRes)
def send_offer_route(payload: SendOfferReq, request: Request):
    # A real e-mail leaves the LLC's own mailbox, so every attempt is audited
    # (never the recipient's address) and capped per hour per caller.
    ip = client_ip(request)
    if count_recent("send_offer", 60, ip=ip) >= send_offer_limit():
        audit("send_offer", request, detail={"ok": False, "reason": "rate_limited"})
        raise HTTPException(status_code=429, detail="Too many offers sent in the last hour; try again later.")
    logger.info("Received send-offer request")
    try:
        success, message = send_offer_email(payload)
        audit("send_offer", request, detail={"ok": bool(success)})
        if not success:
            logger.error(f"Email send failed: {message}")
            raise HTTPException(status_code=500, detail=f"Failed to send email: {message}")
        logger.info("Email send completed successfully")
        return SendOfferRes(message=message, success=success)
    except HTTPException:
        raise
    except Exception:
        ref = uuid.uuid4().hex[:12]
        logger.exception("Unexpected error in send_offer_route ref=%s", ref)
        raise HTTPException(status_code=500, detail=f"Internal server error (ref {ref})")
