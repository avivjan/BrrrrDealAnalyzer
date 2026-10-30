"""`BrrrResultsWithIntermediates` -- every number the BRRRR calculation produces, in one frozen record.

Built by `compute_brrr_with_intermediates` in `BL/analyze/analyzeBRRR.py`. Holds computed values
only (inputs stay on the request payload). The explanation layer
(`BL/analyze/explain/brrr.py`) reads from this record and never recomputes;
`tests/test_explain.py` fails if a field is added here and not explained there.

All money is in plain dollars, as `Decimal`, unrounded. Day counts are ints, dates are
`datetime.date` (every deal has a buy closing date). "Effective" means the user's
value or the formula default when the input was left None.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


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
    buy_closing_date: date
    refi_closing_date: date
    tenant_occupied_date: date
    rehab_completed_date: date
    hml_interest_days_prepaid_at_purchase_closing: int
    hml_interest_days_paid_monthly: int
    hml_interest_days_accrued_into_refi_payoff: int
    hml_interest_monthly_payment_dates: tuple[date, ...]   # each 1st paying the month before it, strictly before the refi
    dscr_interest_days_prepaid_at_refi_closing: int
    first_of_month_dates_after_closing_through_refi: tuple[date, ...]   # HOA and insurance paid monthly: the 1sts in (closing, refi]
    utility_bill_dates_until_refi: tuple[date, ...]       # the 1sts in (closing, min(tenant, refi)] + the arrears bill if on or before the refi
    rent_collection_dates_before_refi: tuple[date, ...]   # the 1sts in (tenant occupied, refi]

    # -- hard money and holding, until the refinance --------------------------
    hml_points: Decimal             # points paid in cash on hml_amount
    hml_per_diem: Decimal
    hml_interest: Decimal           # total per-diem interest until the refi
    prepaid_interest_buy: Decimal   # collected at the buy closing (closing day -> month end)
    hml_interest_paid_monthly: Decimal
    hml_interest_accrued_into_refi_payoff: Decimal   # 1st of the refi month -> day before payoff
    hoa_dues_until_refi: Decimal    # HOA x the 1sts in (closing, refi] (taxes and insurance are paid as bills and deposits below)
    utilities_until_rented: Decimal # utilities x the utility bill 1sts
    pre_refi_rental_income: Decimal # rent x the 1sts in (tenant occupied, refi]

    # -- insurance, purchase to refi ------------------------------------------
    insurance_bill_at_purchase_inside_closing: Decimal    # a line of the purchase settlement
    insurance_bill_at_purchase_outside_closing: Decimal   # paid separately; in Total Cash Invested
    insurance_paid_monthly_until_refi: Decimal            # monthly x the 1sts in (closing, refi]
    insurance_bill_at_refi: Decimal                       # effective: input or the bill at purchase
    insurance_bill_at_refi_inside_closing: Decimal        # a line of the refi settlement (both wires)
    insurance_bill_at_refi_outside_closing: Decimal       # paid separately; in Total Cash Invested

    # -- the property's tax bucket, purchase to refi --------------------------
    property_tax_bill_paid_on_november_30: Decimal        # this year's bill x 0.96
    first_property_tax_payment_date: date                 # the first Nov 30 the owner pays
    property_tax_bucket_deposit_count_until_first_payment: int    # the 15ths after closing through it (1 when none is left)
    property_tax_bucket_deposit: Decimal                  # effective: input or the formula
    property_tax_bucket_first_bill_deposit_dates_until_refi: tuple[date, ...]
    property_tax_bucket_first_bill_deposit_count_until_refi: Decimal   # of those deposits, the ones on or before the refi
    property_tax_bucket_deposit_after_first_payment: Decimal      # bill x 0.96 / 12 after a Nov 30 inside the hold
    property_tax_bucket_later_deposit_dates_until_refi: tuple[date, ...]
    property_tax_bucket_later_deposit_count_until_refi: int
    property_tax_paid_into_bucket_until_refi: Decimal     # every deposit until the refi
    property_tax_bucket_shortfall_topped_up_on_november_30: Decimal
    property_tax_lump_sum_at_refi_closing: Decimal        # 0 unless the refi lender collects the whole bill
    property_tax_bucket_balance_released_at_refi: Decimal # comes back with the lump; 0 otherwise

    # -- the purchase settlement -------------------------------------------------
    deed_transfer_tax_buy: Decimal  # $0 standard; 0.70% of the price when we pay all closing costs
    recording_transfer_buy: Decimal # effective
    title_escrow_buy: Decimal       # effective
    notary_buy: Decimal
    closing_costs_buy_total: Decimal
    seller_paid_current_year_taxes: bool   # effective
    seller_tax_credit_formula: Decimal   # the proration by the closing date
    seller_tax_credit: Decimal      # effective: input or the formula; positive = credit to the buyer
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
    hysa_deposit_at_refi: Decimal   # effective: input or 3 months of principal and interest
    reserves_total: Decimal         # maintenance + vacancy + capex + HYSA; the owner's, counted as equity

    # -- cash out at the refinance --------------------------------------------
    hml_payoff: Decimal             # hml_amount + accrued interest
    appraisal_and_survey_paid_outside_closing: Decimal   # at the end of the rehab, POC on the refi statement
    total_cash_invested: Decimal    # everything spent before the refi, plus the credit set aside in the tax bucket
    cash_out_routi: Decimal         # the refi wire ("Due to Borrower"; the reserves are not taken off it)
    cash_out_routi_conservative: Decimal      # the wire at the lowest ARV
    cash_to_refi_table_conservative: Decimal  # max(0, -cash_out_routi_conservative)
    reserves_funded_from_own_pocket_at_lowest_arv: Decimal   # max(0, reserves - max(0, cash_out_routi_conservative))
    cash_out: Decimal               # cash_out_routi - reserves_total - total_cash_invested

    # -- monthly, after the refinance -----------------------------------------
    vacancy: Decimal                # rent x vacancy %
    management_fee: Decimal         # rent x property management %
    maintenance: Decimal            # rent x maintenance %
    capex: Decimal                  # rent x capex %
    monthly_taxes: Decimal          # this year's bill x 0.96 / 12: the refi never changes the tax
    monthly_insurance: Decimal      # effective: input or the insurance bill at the refi / 12
    operating_expenses: Decimal     # the six above + HOA
    mortgage_payment: Decimal
    net_operating_income: Decimal   # rent minus operating expenses
    cash_flow: Decimal              # NOI minus mortgage payment
    pitia: Decimal                  # mortgage + monthly taxes + monthly insurance + HOA
    dscr: Decimal                   # rent / pitia (0 when pitia is 0)

    # -- returns --------------------------------------------------------------
    cash_on_cash: Decimal           # percent; -1 = infinite, -2 = undefined
    equity: Decimal                 # arv x (1 - ltv) + reserves_total
    net_profit: Decimal             # equity + cash_out
    roi: Decimal                    # percent; -1 = infinite, -2 = undefined

    # -- cash needed -----------------------------------------------------------
    total_cash_needed: Decimal      # total_cash_invested + rehab cushion + cash_to_refi_table_conservative + reserves_funded_from_own_pocket_at_lowest_arv, to the cent
