"""`BrrrResultsWithIntermediates` -- every number the BRRRR calculation produces, in one frozen record.

Built by `compute_brrr_with_intermediates` in `BL/analyze/analyzeBRRR.py`. Holds computed values
only (inputs stay on the request payload). The explanation layer
(`BL/analyze/explain/brrr.py`) reads from this record and never recomputes;
`tests/test_explain.py` fails if a field is added here and not explained there.

All money is in plain dollars, as `Decimal`, unrounded. Day counts are ints, dates are
`datetime.date` (None when the deal has no buy closing date). "Effective" means the user's
value or the formula default when the input was left None.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class BrrrResultsWithIntermediates:
    # -- dollar basis ---------------------------------------------------------
    arv: Decimal
    lowest_arv: Decimal             # effective: input or 90% of ARV
    purchase_price: Decimal
    rehab_cost_base: Decimal        # rehab before contingency
    rehab_contingency: Decimal      # rehab_cost_base x contingency %
    rehab_cost: Decimal             # rehab_cost_base + rehab_contingency
    construction_budget: Decimal    # rehab financed by the hard-money lender

    # -- the hard-money stack ---------------------------------------------------
    purchase_loan_amount: Decimal   # purchase x (1 - down %)
    down_payment_cash: Decimal
    hml_amount: Decimal             # purchase loan + construction budget; principal at payoff

    # -- timeline ---------------------------------------------------------------
    buy_closing_date: Optional[date]
    refi_closing_date: Optional[date]
    tenant_occupied_date: Optional[date]
    hml_interest_days_prepaid_at_purchase_closing: int
    hml_interest_days_paid_monthly: int
    hml_interest_days_accrued_into_refi_payoff: int
    dscr_interest_days_prepaid_at_refi_closing: int
    days_tenant_occupied_before_refi: int

    # -- hard money and holding, until the refinance --------------------------
    hml_points: Decimal             # points paid in cash on hml_amount
    hml_per_diem: Decimal
    hml_interest: Decimal           # total per-diem interest until the refi
    prepaid_interest_buy: Decimal   # collected at the buy closing (closing day -> month end)
    hml_interest_paid_monthly: Decimal
    hml_interest_accrued_into_refi_payoff: Decimal   # 1st of the refi month -> day before payoff
    holding_costs: Decimal          # taxes + insurance + HOA accrued until the refi
    utilities_until_rented: Decimal
    pre_refi_rental_income: Decimal # rent from tenant placement to the refi

    # -- the purchase settlement -------------------------------------------------
    deed_transfer_tax_buy: Decimal  # $0 standard; 0.70% of the price when we pay all closing costs
    recording_transfer_buy: Decimal # effective
    title_escrow_buy: Decimal       # effective
    notary_buy: Decimal
    closing_costs_buy_total: Decimal
    seller_paid_current_year_taxes: Optional[bool]   # effective; None without a closing date
    seller_tax_credit: Decimal      # positive = credit to the buyer
    seller_tax_credit_set_aside_in_tax_bucket: Decimal   # max(0, credit): in the tax bucket the day after closing
    cash_to_close_buy: Decimal      # the wire on purchase day
    total_hard_money_cost: Decimal  # points + interest + loan charges (buy)

    # -- rehab draws --------------------------------------------------------------
    stolen_money: Decimal           # construction budget - rehab cost (signed)
    rehab_paid_cash_out_of_pocket: Decimal             # rehab cost - construction budget (signed; the invested term)

    # -- refinance terms ------------------------------------------------------
    ltv: Decimal                    # as a fraction (0.75)
    refi_loan_amount: Decimal       # arv x ltv
    conservative_refi_loan_amount: Decimal   # lowest_arv x ltv
    broker_points_refi: Decimal
    broker_points_refi_conservative: Decimal
    recording_transfer_refi: Decimal          # effective
    recording_transfer_refi_conservative: Decimal
    title_escrow_refi: Decimal                # effective
    title_escrow_refi_conservative: Decimal
    notary_refi: Decimal
    closing_costs_refi_total: Decimal
    closing_costs_refi_total_conservative: Decimal
    prepaid_interest_refi: Decimal
    prepaid_interest_refi_conservative: Decimal
    vacancy_reserve: Decimal        # effective: input or one month of rent
    reserves_total: Decimal         # maintenance + vacancy + capex; recoverable, counted as equity

    # -- cash out at the refinance --------------------------------------------
    hml_payoff: Decimal             # hml_amount + accrued interest
    total_cash_invested: Decimal    # everything spent before the refi, plus the credit set aside in the tax bucket
    cash_out_routi: Decimal         # the refi wire
    cash_out_routi_conservative: Decimal      # the wire at the lowest ARV
    cash_to_refi_table_conservative: Decimal  # max(0, -cash_out_routi_conservative)
    cash_out: Decimal               # cash_out_routi - total_cash_invested

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
    equity: Decimal                 # arv x (1 - ltv) + reserves_total
    net_profit: Decimal             # equity + cash_out
    roi: Decimal                    # percent; -1 = infinite, -2 = undefined

    # -- cash needed -----------------------------------------------------------
    total_cash_needed: Decimal      # total_cash_invested + rehab cushion + cash_to_refi_table_conservative
