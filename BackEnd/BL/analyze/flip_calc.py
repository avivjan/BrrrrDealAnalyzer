"""`FlipCalc` -- every number the fix-and-flip calculation produces, in one frozen record.

Built by `compute_flip` in `BL/analyze/analyzeFlip.py`. Holds computed values
only (inputs stay on the request payload). The explanation layer
(`BL/analyze/explain/flip.py`) reads from this record and never recomputes;
`tests/test_explain.py` fails if a field is added here and not explained there.

All money is in plain dollars, as `Decimal`, unrounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class FlipCalc:
    # -- dollar basis ---------------------------------------------------------
    purchase_price: Decimal
    sale_price: Decimal
    closing_costs_buy: Decimal
    rehab_cost_base: Decimal        # rehab before contingency
    rehab_contingency: Decimal      # rehab_cost_base x contingency %
    rehab_cost: Decimal             # rehab_cost_base + rehab_contingency

    # -- hard money over the hold ---------------------------------------------
    hml_amount: Decimal             # purchase loan (+ rehab when HM funds it)
    hml_points: Decimal             # points paid in cash on hml_amount
    monthly_hml_interest: Decimal
    total_hml_interest: Decimal     # monthly x holding months

    # -- operating and holding costs over the hold ----------------------------
    monthly_taxes: Decimal
    monthly_insurance: Decimal
    monthly_operating: Decimal      # taxes/12 + insurance/12 + HOA + utilities
    total_operating: Decimal        # monthly x holding months
    total_holding_costs: Decimal    # total_hml_interest + total_operating

    # -- selling ----------------------------------------------------------------
    agent_fees_percent: Decimal     # buyer + seller agent fee, in percent
    selling_closing_costs: Decimal
    selling_costs: Decimal          # sale x agent fees + selling closing costs

    # -- lifetime cash requirement --------------------------------------------
    down_payment_cash: Decimal
    rehab_cash: Decimal             # rehab paid out of pocket (0 when HM funds it)
    total_cash_needed: Decimal
    total_cash_needed_with_buffer: Decimal
    rehab_float: Decimal            # 10% of rehab kept on hand for draws
    buffered_closing: Decimal       # closing x 1.1
    buffered_operating: Decimal     # operating x 1.5
    buffered_interest: Decimal      # HML interest x 1.5

    # -- profit -----------------------------------------------------------------
    total_cash_invested: Decimal    # down + closing + points + holding + rehab cash
    total_cost_basis: Decimal       # purchase + rehab + closing + holding + selling + points
    gross_profit: Decimal           # sale - cost basis
    capital_gains_tax: Decimal      # on a positive gross profit only
    net_profit: Decimal             # gross - tax

    # -- returns --------------------------------------------------------------
    holding_years: Decimal
    roi: Decimal                    # percent; -1 = infinite, -2 = -infinite
    annualized_roi: Decimal
