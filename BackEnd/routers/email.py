"""POST /send-offer."""

import logging

from fastapi import APIRouter, HTTPException

from ReqRes.email.sendOffer.sendOfferReq import SendOfferReq
from ReqRes.email.sendOffer.sendOfferRes import SendOfferRes
from BL.email.sendOffer.sendOffer import send_offer_email

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/send-offer", response_model=SendOfferRes)
def send_offer_route(payload: SendOfferReq):
    logger.info(f"Received send-offer request: property={payload.property_address}, agent={payload.agent_name}, email={payload.agent_email}")
    try:
        success, message = send_offer_email(payload)
        if not success:
            logger.error(f"Email send failed: {message}")
            raise HTTPException(status_code=500, detail=f"Failed to send email: {message}")
        logger.info("Email send completed successfully")
        return SendOfferRes(message=message, success=success)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_offer_route: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
