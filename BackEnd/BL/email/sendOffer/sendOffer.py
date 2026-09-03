"""The `/send-offer` orchestrator is `send_offer_email` itself -- there is no
additional business logic beyond composing and sending the message. The
try/except -> HTTPException translation is an HTTP concern and stays in the
router."""

from BL.email.common.offer_email import send_offer_email  # noqa: F401
