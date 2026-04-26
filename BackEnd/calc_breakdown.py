"""Calculation breakdown primitives.

These types let calculation functions document themselves "between the lines":
each intermediate variable can register a `CalcStep` next to where it is
computed, grouped under one or more high-level metric keys (e.g. `cash_flow`,
`roi`, `net_profit`). The final response carries a `breakdowns` dict keyed by
metric so the frontend can render hover/PDF explanations without recomputing
anything.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Union

from pydantic import BaseModel


Number = Union[Decimal, float, int]


def fmt_money(value: Number) -> str:
    """Render a dollar value with thousands separators and 0-2 decimals."""
    v = float(value)
    if v == int(v):
        return f"${int(v):,}"
    return f"${v:,.2f}"


def fmt_pct(value: Number, decimals: int = 2) -> str:
    """Render a percentage value with the given decimal precision."""
    return f"{float(value):.{decimals}f}%"


def fmt_num(value: Number, decimals: int = 2) -> str:
    """Render a plain number (e.g. DSCR ratio)."""
    return f"{float(value):.{decimals}f}"


class CalcStep(BaseModel):
    """A single self-documenting line in a calculation.

    `label`   - human-readable name of the variable ("Operating Expenses").
    `value`   - the numeric result of the step (always a float for JSON).
    `formula` - the literal expression evaluated, with concrete values
                substituted (e.g. "$2000 - $800 - $1000 = $200").
    """

    label: str
    value: float
    formula: str


class CalcBreakdown:
    """Accumulator that lets calculation functions log steps inline.

    Steps are stored under one or more metric keys so the frontend can pull
    only the lines relevant to a given result (Cash Flow, ROI, Net Profit, ...).
    The same step can contribute to multiple metrics (e.g. mortgage payment is
    used by both `cash_flow` and `dscr`) by passing a list of keys.
    """

    def __init__(self) -> None:
        self._steps: dict[str, list[CalcStep]] = {}

    def add(
        self,
        keys: Union[str, Iterable[str]],
        label: str,
        value: Number,
        formula: str,
    ) -> None:
        if isinstance(keys, str):
            keys = (keys,)
        step = CalcStep(label=label, value=float(value), formula=formula)
        for k in keys:
            self._steps.setdefault(k, []).append(step)

    def to_dict(self) -> dict[str, list[dict]]:
        """Serialize for inclusion in a Pydantic response model."""
        return {k: [s.model_dump() for s in v] for k, v in self._steps.items()}
