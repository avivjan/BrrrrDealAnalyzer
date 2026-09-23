"""The percent-rate columns, grouped by table.

Lenders quote rates in eighths of a percent (7.125%). ``NUMERIC(5, 2)`` rounded such a rate to
7.13 on the way into the row, so a saved deal recomputed with a rate the owner never typed and
disagreed with the calculator by cents. ``NUMERIC(6, 3)`` stores the typed rate exactly.
Shared between the runtime migration (:mod:`migrations.steps.widen_rate_columns`) and any
offline preflight tooling.
"""

RATE_COLUMNS_BY_TABLE = {
    "active_deals": ("down_payment", "HML_points", "HML_interest_rate", "refi_points", "ltv_as_precent", "interest_rate"),
    "bought_brrrr_deals": ("down_payment", "HML_points", "HML_interest_rate", "refi_points", "ltv_as_precent", "interest_rate"),
    "flip_deals": ("down_payment", "HML_points", "HML_interest_rate"),
    "bought_flip_deals": ("down_payment", "HML_points", "HML_interest_rate"),
}

RATE_COLUMN_SCALE = 3
