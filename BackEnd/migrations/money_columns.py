"""The `*_in_thousands` money columns, grouped by table.

Money is stored in thousands, so ``NUMERIC(_, 2)`` rounds to the nearest $10 and
cannot hold a $50,500 purchase price. Widening the scale to 4 is lossless in
Postgres. Shared between the runtime migration (:mod:`migrations.steps.widen_money_columns`)
and any offline preflight tooling.
"""

MONEY_COLUMNS_BY_TABLE = {
    "active_deals": (
        "purchase_price_in_thousands", "rehab_cost_in_thousands",
        "closing_costs_buy_in_thousands", "arv_in_thousands",
        "closing_cost_refi_in_thousands", "cash_reserve_in_thousands",
    ),
    "bought_brrrr_deals": (
        "purchase_price_in_thousands", "rehab_cost_in_thousands",
        "closing_costs_buy_in_thousands", "arv_in_thousands",
        "closing_cost_refi_in_thousands", "cash_reserve_in_thousands",
    ),
    "flip_deals": (
        "purchase_price_in_thousands", "rehab_cost_in_thousands",
        "closing_costs_buy_in_thousands", "sale_price_in_thousands",
        "selling_closing_costs_in_thousands",
    ),
    "bought_flip_deals": (
        "purchase_price_in_thousands", "rehab_cost_in_thousands",
        "closing_costs_buy_in_thousands", "sale_price_in_thousands",
        "selling_closing_costs_in_thousands",
    ),
}
