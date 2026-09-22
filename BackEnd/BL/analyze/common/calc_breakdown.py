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

    def __init__(self, results_record=None) -> None:
        self._steps: dict[str, list[CalcStep]] = {}
        # Every step value, by the identity of the Decimal object it was added with, to the
        # (label, section keys) of the steps carrying it. The explain layer reads each value off the
        # frozen results record and later passes the very same object as an operand of a sum, which is
        # what lets `add_sum` stamp that operand with the step it came from, without any narrative edit.
        self._step_labels_by_value_object_id: dict[int, list[tuple[str, frozenset[str]]]] = {}
        # A Decimal object the record stores under two different fields (the default notary fee
        # constant backing both legs; a typed refi line reused at the lowest ARV) is not one value:
        # it may only link inside a section its step was added to. `vars()`, not `getattr` over
        # `dataclasses.fields`: the reads proxy in tests/test_explain.py logs attribute reads, and
        # this bookkeeping must not count as "explaining" a field.
        record_fields = vars(results_record).values() if results_record is not None else ()
        seen_once: set[int] = set()
        self._value_object_ids_backing_two_record_fields: set[int] = set()
        for field_value in record_fields:
            if not isinstance(field_value, Decimal):
                continue
            if id(field_value) in seen_once:
                self._value_object_ids_backing_two_record_fields.add(id(field_value))
            seen_once.add(id(field_value))

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
        keys = (keys,) if isinstance(keys, str) else tuple(keys)
        if isinstance(value, Decimal):  # before float(): the identity is that of the Decimal object
            self._step_labels_by_value_object_id.setdefault(id(value), []).append((label, frozenset(keys)))
        step = CalcStep(label=label, value=float(value), unit=unit, formula=formula, terms=terms, note=note)
        for k in keys:
            self._steps.setdefault(k, []).append(step)

    def _linked_step_label(self, operand_value: Number, sum_step_keys: frozenset[str]) -> Optional[str]:
        """The label of the step this operand is the value of, or None for a raw input.

        A step filed under one of the sum's own sections wins; otherwise an object that backs two
        record fields is ambiguous and stays unlinked; otherwise the sole step carrying it (a
        cross-section link, e.g. a flip's Total Cash Invested reaching Total Holding Costs).
        """
        candidates = self._step_labels_by_value_object_id.get(id(operand_value)) or []
        for step_label, step_keys in candidates:
            if step_keys & sum_step_keys:
                return step_label
        if id(operand_value) in self._value_object_ids_backing_two_record_fields:
            return None
        return candidates[0][0] if candidates else None

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
        sum_step_keys = frozenset((keys,) if isinstance(keys, str) else keys)
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
            terms=[
                CalcTerm(label=name, value=float(value), sign=sign, step_label=self._linked_step_label(value, sum_step_keys))
                for name, value, sign in norm
            ],
        )

    def to_dict(self) -> dict[str, list[dict]]:
        """Serialize for inclusion in a Pydantic response model."""
        return {k: [s.model_dump() for s in v] for k, v in self._steps.items()}
