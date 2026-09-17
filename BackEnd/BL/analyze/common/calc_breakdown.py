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
from typing import Iterable, Literal, Optional, Union

from ReqRes.common.calc_step import CalcStep, CalcTerm

Number = Union[Decimal, float, int]
Unit = Literal["money", "pct", "ratio"]
# A term of a sum step: (label, value) or (label, value, "-") for a subtracted one.
Term = Union[tuple[str, Number], tuple[str, Number, str]]


def fmt_money(value: Number) -> str:
    """Render a dollar value with thousands separators and 0-2 decimals (-$1,200.50)."""
    v = float(value)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v == int(v):
        return f"{sign}${int(v):,}"
    return f"{sign}${v:,.2f}"


def fmt_pct(value: Number, decimals: int = 2) -> str:
    """Render a percentage with up to `decimals` decimals, trailing zeros dropped (75%, 6.5%, 19.87%)."""
    text = f"{float(value):.{decimals}f}".rstrip("0").rstrip(".")
    return f"{text}%"


def fmt_num(value: Number, decimals: int = 2) -> str:
    """Render a plain number (e.g. DSCR ratio) with a fixed number of decimals."""
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
        unit: Unit = "money",
        note: Optional[str] = None,
        terms: Optional[list[CalcTerm]] = None,
    ) -> None:
        if isinstance(keys, str):
            keys = (keys,)
        step = CalcStep(label=label, value=float(value), unit=unit, formula=formula, terms=terms, note=note)
        for k in keys:
            self._steps.setdefault(k, []).append(step)

    def add_sum(
        self,
        keys: Union[str, Iterable[str]],
        label: str,
        total: Number,
        terms: Iterable[Term],
        note: Optional[str] = None,
    ) -> None:
        """A sum-type step: guard, formula text and structured terms in one go.

        `terms` are (label, value) or (label, value, "-") in the same
        left-to-right order the calculator adds them, and the guard folds them
        in that order with plain `==` on the unrounded Decimals. So if the
        calculation gains, drops or reorders an operand and this list is not
        updated, the mismatch raises here instead of printing a wrong formula.
        """
        norm = [(t[0], t[1], t[2] if len(t) > 2 else "+") for t in terms]
        acc = norm[0][1] if norm[0][2] == "+" else -norm[0][1]
        for _, value, sign in norm[1:]:
            acc = acc + value if sign == "+" else acc - value
        check(acc == total, label)

        text = f"{norm[0][0]} ({fmt_money(norm[0][1])})"
        for name, value, sign in norm[1:]:
            text += f" {'+' if sign == '+' else '−'} {name} ({fmt_money(value)})"
        text += f" = {fmt_money(total)}"
        self.add(
            keys, label, total, text, note=note,
            terms=[CalcTerm(label=name, value=float(value), sign=sign) for name, value, sign in norm],
        )

    def to_dict(self) -> dict[str, list[dict]]:
        """Serialize for inclusion in a Pydantic response model."""
        return {k: [s.model_dump() for s in v] for k, v in self._steps.items()}
