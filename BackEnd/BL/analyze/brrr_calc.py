"""`BrrrCalc` -- every number the BRRRR calculation produces, in one frozen record.

Built by `compute_brrr` in `BL/analyze/analyzeBRRR.py`. Holds computed values
only (inputs stay on the request payload). The explanation layer
(`BL/analyze/explain/brrr.py`) reads from this record and never recomputes;
`tests/test_explain.py` fails if a field is added here and not explained there.

All money is in plain dollars, as `Decimal`, unrounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BrrrCalc:
    # -- dollar basis ---------------------------------------------------------
    arv: Decimal
    purchase_price: Decimal
    rehab_cost_base: Decimal        # rehab before contingency
    rehab_contingency: Decimal      # rehab_cost_base x contingency %
    rehab_cost: Decimal             # rehab_cost_base + rehab_contingency

    # -- hard money and holding, until the refinance --------------------------
    hml_amount: Decimal             # purchase loan (+ rehab when HM funds it); paid off at refi
    hml_points: Decimal             # points paid in cash on hml_amount
    hml_interest: Decimal           # per-diem interest accrued until the refi
    holding_costs: Decimal          # taxes + insurance + HOA accrued until the refi

    # -- refinance terms ------------------------------------------------------
    closing_costs_buy: Decimal
    closing_costs_refi: Decimal
    ltv: Decimal                    # as a fraction (0.75)
    refi_points: Decimal            # points paid in cash on the refi loan
    cash_reserve: Decimal           # escrowed at refi, recoverable (counted as equity)

    # -- cash out at the refinance --------------------------------------------
    loan_amount: Decimal            # arv x ltv
    down_payment_cash: Decimal
    rehab_cash: Decimal             # rehab paid out of pocket (0 when HM funds it)
    total_cash_invested: Decimal    # everything put in before the refi
    cash_out_routi: Decimal         # the refi wire: loan minus payoff, refi costs, reserve
    cash_out: Decimal               # cash_out_routi minus total_cash_invested

    # -- monthly, after the refinance -----------------------------------------
    vacancy: Decimal                # rent x vacancy %
    management_fee: Decimal         # rent x property management %
    maintenance: Decimal            # rent x maintenance %
    capex: Decimal                  # rent x capex %
    monthly_taxes: Decimal
    monthly_insurance: Decimal
    operating_expenses: Decimal     # the six above + HOA
    mortgage_payment: Decimal
    net_operating_income: Decimal   # rent minus operating expenses
    cash_flow: Decimal              # NOI minus mortgage payment
    pitia: Decimal                  # mortgage + taxes/12 + insurance/12 + HOA
    dscr: Decimal                   # rent / pitia (0 when pitia is 0)

    # -- returns --------------------------------------------------------------
    cash_on_cash: Decimal           # percent; -1 = infinite, -2 = undefined
    equity: Decimal                 # arv x (1 - ltv) + cash_reserve
    net_profit: Decimal             # equity + cash_out
    roi: Decimal                    # percent; -1 = infinite, -2 = undefined

    # -- lifetime cash requirement --------------------------------------------
    refi_shortfall: Decimal         # max(0, -cash_out_routi): cash brought to the refi table
    total_cash_needed: Decimal
    total_cash_needed_with_buffer: Decimal
    rehab_float: Decimal            # 10% of rehab kept on hand for draws
    buffered_closing: Decimal       # closing x 1.1
    buffered_holding: Decimal       # holding x 1.5
    buffered_interest: Decimal      # HML interest x 1.5
