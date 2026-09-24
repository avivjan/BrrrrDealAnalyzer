"""The calculation breakdown as a tree, answer first: the PDF's copy of the popup's shape.

A one-to-one port of `frontend/src/components/deal/calculationBreakdownTree.ts`, so each
report section is built from exactly the rows the website's `CalculationBreakdownPopup`
shows for the same tile. The two implementations are pinned to one shared fixture
(`frontend/src/components/deal/__fixtures__/calculationBreakdownTreeParity.json`), which
both test suites rebuild and compare.

Steps and terms are the plain dicts of a response's `breakdowns`. Nothing here computes a
number: it only reshapes the engine's own steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CalcBreakdowns = dict[str, list[dict]]


@dataclass(frozen=True)
class CalculationBreakdownRow:
    path: str
    # "+" / "-" for an operand; None for a step listed as an input of a non-sum headline.
    sign: Optional[str]
    label: str
    value: float
    unit: str
    # The step this row is the value of; present exactly when the row can be expanded.
    linked_step: Optional[dict] = None


def find_headline_step_index(steps: list[dict], metric_value: Optional[float]) -> int:
    """The step that *is* the tile's number: the last one whose value equals it, else the last step."""
    if not steps:
        return -1
    if metric_value is not None:
        for index in range(len(steps) - 1, -1, -1):
            if steps[index].get("value") == metric_value:
                return index
    return len(steps) - 1


def find_step_by_label(breakdowns: CalcBreakdowns, preferred_section_key: str, label: str) -> Optional[dict]:
    """The step carrying `label`: the section it was referenced from first, then every section in order."""
    for step in breakdowns.get(preferred_section_key) or []:
        if step.get("label") == label:
            return step
    for steps in breakdowns.values():
        for step in steps or []:
            if step.get("label") == label:
                return step
    return None


def is_sum_step(step: dict) -> bool:
    return bool(step.get("terms"))


def rows_of_step(
    step: dict,
    breakdowns: CalcBreakdowns,
    section_key: str,
    parent_path: str,
    ancestor_step_labels: frozenset[str] | set[str],
) -> list[CalculationBreakdownRow]:
    """One row per operand of a sum step, linked to its source step when the backend named one
    and that step is not already an ancestor (the cycle guard). A non-sum step has no rows."""
    if not is_sum_step(step):
        return []
    rows = []
    for index, term in enumerate(step["terms"]):
        term_step_label = term.get("step_label")
        linked_step = (
            find_step_by_label(breakdowns, section_key, term_step_label)
            if term_step_label and term_step_label not in ancestor_step_labels
            else None
        )
        rows.append(CalculationBreakdownRow(
            path=f"{parent_path}/{index}" if parent_path else str(index),
            sign=term.get("sign", "+"),
            label=term.get("label", ""),
            value=term.get("value"),
            unit=(linked_step.get("unit") or "money") if linked_step else "money",
            linked_step=linked_step,
        ))
    return rows


def rows_of_steps(steps: list[dict], path_prefix: str) -> list[CalculationBreakdownRow]:
    """Steps of the section listed as expandable rows (a non-sum headline's inputs, or the steps derived after it)."""
    return [
        CalculationBreakdownRow(
            path=f"{path_prefix}/{index}",
            sign=None,
            label=step.get("label", ""),
            value=step.get("value"),
            unit=step.get("unit") or "money",
            linked_step=step,
        )
        for index, step in enumerate(steps)
    ]


def top_level_rows_for_headline(
    breakdowns: CalcBreakdowns, section_key: str, headline_index: int,
) -> list[CalculationBreakdownRow]:
    """A sum headline shows its operands; a non-sum headline shows the section's earlier steps."""
    steps = breakdowns.get(section_key) or []
    if headline_index < 0 or headline_index >= len(steps):
        return []
    headline = steps[headline_index]
    if is_sum_step(headline):
        return rows_of_step(headline, breakdowns, section_key, "", frozenset({headline.get("label")}))
    return rows_of_steps(steps[:headline_index], "input")


def steps_after_headline(steps: list[dict], headline_index: int) -> list[dict]:
    return steps[headline_index + 1:] if headline_index >= 0 else []


def child_ancestor_step_labels(
    row: CalculationBreakdownRow, ancestor_step_labels: frozenset[str] | set[str],
) -> frozenset[str]:
    """The ancestors a row's children see: the row's own ancestors plus its linked step."""
    labels = set(ancestor_step_labels)
    if row.linked_step is not None:
        labels.add(row.linked_step.get("label"))
    return frozenset(labels)


def all_expandable_row_paths(
    rows: list[CalculationBreakdownRow],
    breakdowns: CalcBreakdowns,
    section_key: str,
    ancestor_step_labels: frozenset[str] | set[str],
) -> list[str]:
    """Every expandable path under `rows`, recursively ("Expand all")."""
    paths: list[str] = []
    for row in rows:
        if row.linked_step is None:
            continue
        paths.append(row.path)
        ancestors = child_ancestor_step_labels(row, ancestor_step_labels)
        children = rows_of_step(row.linked_step, breakdowns, section_key, row.path, ancestors)
        paths.extend(all_expandable_row_paths(children, breakdowns, section_key, ancestors))
    return paths


def default_expanded_row_paths(rows: list[CalculationBreakdownRow]) -> list[str]:
    """The paths open when the popup appears: every expandable row of the first level."""
    return [row.path for row in rows if row.linked_step is not None]
