"""Shared calculation breakdown primitives used by analyze responses.

`CalcStep` records one intermediate value computed by the analyzers along with
a human-readable formula string. Keeping these structured (rather than a list
of pre-rendered strings) lets the frontend filter by `key` for hover-to-reveal
tooltips and lets the PDF report group steps into sections.
"""

from typing import Optional
from pydantic import BaseModel


class CalcStep(BaseModel):
    """One labeled intermediate value in a calculation breakdown.

    Fields:
        key:     Stable identifier used by the frontend to look up this step
                 (e.g. ``"cash_flow"``, ``"mortgage_payment"``). Optional for
                 internal-only steps that don't need a UI surface.
        label:   Human-readable name shown in PDF reports / detail lists.
        value:   Numeric value of this intermediate result (in dollars or %).
        formula: Plain-English formula string with the substituted values
                 (e.g. ``"Rent ($2,000) - OpEx ($800) - Mortgage ($1,000) = $200"``).
    """

    key: Optional[str] = None
    label: str
    value: float
    formula: str
