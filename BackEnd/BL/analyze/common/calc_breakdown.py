"""Calculation breakdown primitives, used by the explain layer (`BL/analyze/explain/`).

`CalcBreakdown` accumulates `CalcStep`s under one or more high-level metric
keys (e.g. `cash_flow`, `roi`, `net_profit`); the final response carries the
resulting `breakdowns` dict, which the PDF report renders and the API / MCP
pass through. `check` is the drift guard: the explain layer states each
equation it is about to narrate, and a mismatch with the calculated record
raises `CalcExplainMismatch` instead of printing a wrong explanation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Union

from ReqRes.common.calc_step import CalcStep

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


class CalcExplainMismatch(ValueError):
    """The explanation's equation no longer matches what the calculator computed."""


def check(condition: bool, step: str) -> None:
    """Drift guard. An explicit raise, not `assert`: it must survive `python -O`.

    The message names the step only, never the numbers, so a failure that
    surfaces as an HTTP 500 carries no deal data.
    """
    if not condition:
        raise CalcExplainMismatch(f"explanation out of sync with the calculation at step: {step}")


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
