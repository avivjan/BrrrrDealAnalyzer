"""Backward compatibility for the `use_HM_for_rehab` -> `constructionLoanBudget` change.

The BRRRR calc used to finance either all of the rehab (with contingency) or none of it, by a
boolean. It now takes an explicit construction-loan budget. A payload from a stale cached
frontend (or an old saved request) still speaks the boolean; read as-is the deal would look
cash-funded, so derive the budget it meant instead. Same shape as `refi_timing.py`.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

_BUDGET_KEYS = ("constructionLoanBudget", "construction_loan_budget_in_thousands")
_REHAB_KEYS = ("rehabCost", "rehab_cost_in_thousands")
_CONTINGENCY_KEYS = ("rehabContingency", "rehab_contingency_percent")


def _first_present_value(data: dict, keys) -> Any:
    for key in keys:
        if data.get(key) is not None:
            return data[key]
    return None


def construction_budget_from_legacy_hm_flag(data: Any) -> Any:
    """Fill `constructionLoanBudget` from `use_HM_for_rehab` + rehab, if that's all we got.

    Used as a Pydantic `mode="before"` model validator. Returns `data` untouched unless it is
    a dict with the legacy flag on and no budget of its own.
    """
    if not isinstance(data, dict):
        return data
    if any(data.get(key) is not None for key in _BUDGET_KEYS):
        return data
    if not data.get("use_HM_for_rehab"):
        return data
    rehab_cost_in_thousands = _first_present_value(data, _REHAB_KEYS)
    if rehab_cost_in_thousands is None:
        return data
    rehab_contingency_percent = _first_present_value(data, _CONTINGENCY_KEYS) or 0
    try:
        construction_budget_in_thousands = Decimal(str(rehab_cost_in_thousands)) * (1 + Decimal(str(rehab_contingency_percent)) / Decimal("100"))
    except (InvalidOperation, ValueError, TypeError):
        return data
    return {**data, "constructionLoanBudget": str(construction_budget_in_thousands)}
