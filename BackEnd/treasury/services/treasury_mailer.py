"""Treasury mailer.

Builds the notification payloads the treasury workflows send to operators
and provides a single `send()` seam that tests monkeypatch so no real SMTP
connection is ever opened in the suite. Wiring this to the app-level Gmail
SMTP sender (see `main.py`) is a one-line swap inside `send()`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class MissedRentEmail:
    to: str
    subject: str
    body_text: str
    property_name: str
    pi_amount: Decimal
    approve_url: str
    keep_url: str

    def as_dict(self) -> dict:
        return {
            "to": self.to,
            "subject": self.subject,
            "body_text": self.body_text,
            "property_name": self.property_name,
            "pi_amount": str(self.pi_amount),
            "approve_url": self.approve_url,
            "keep_url": self.keep_url,
        }


def build_missed_rent_email(
    *,
    to: str,
    property_name: str,
    pi_amount: Decimal,
    approve_url: str,
    keep_url: str,
) -> MissedRentEmail:
    """Compose the 8th-of-the-month missed-rent notification."""
    amount = Decimal(pi_amount or 0).quantize(Decimal("0.01"))
    subject = f"Action Required: Missed rent for {property_name}"
    body_text = (
        f"Notice: Rent for {property_name} was not received for this cycle. "
        f"A mortgage P&I draft of ${amount} will execute on the 10th.\n\n"
        f"Action Required: Do you want to execute an Immediate Express Transfer "
        f"from HYSA/Savings -> Checking to cover this draft?\n\n"
        f"[Approve HYSA Transfer] {approve_url}\n"
        f"[Keep Cash in Checking] {keep_url}\n"
    )
    return MissedRentEmail(
        to=to,
        subject=subject,
        body_text=body_text,
        property_name=property_name,
        pi_amount=amount,
        approve_url=approve_url,
        keep_url=keep_url,
    )


def send(email: MissedRentEmail) -> bool:
    """Deliver the email. Default implementation logs only (no network I/O).

    Tests monkeypatch this function to capture the payload; production can
    forward `email` to the Gmail SMTP helper in `main.py`.
    """
    logger.info("Treasury email queued to=%s subject=%s", email.to, email.subject)
    return True
