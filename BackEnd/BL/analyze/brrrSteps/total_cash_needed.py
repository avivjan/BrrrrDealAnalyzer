"""BRRRR step: Cash Needed -- the single definitive out-of-pocket capital through the refi,
never below the day-one floor."""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import calc_hml_interest, calc_holding_costs, DAYS_PER_MONTH


class CashNeeded(NamedTuple):
    hml_interest_first_month_days: int   # 30 less the days already prepaid inside Cash to Close (Buy)
    hml_interest_first_month: Decimal    # the hard-money per diem over those days
    holding_costs_first_month: Decimal   # HOA for 30 days + one month of insurance until refi + one tax-bucket deposit
    cash_needed_floor: Decimal           # EMD + cash to close + insurance bill paid outside it + cushion + one month of utilities, interest and holding costs
    cash_needed_through_refi: Decimal    # total_cash_invested + cushion + cash to the refi table and the reserves it cannot fund, at the lowest ARV
    cash_needed_floor_top_up: Decimal    # max(0, floor - through refi)
    total_cash_needed: Decimal           # max(floor, through refi), written as through refi + top-up


def total_cash_needed_step(payload, hml_amount, buy_settlement, cash_out_figures, timeline, insurance, property_tax_bucket) -> CashNeeded:
    # The floor: what the deal takes on day one and through the first month whatever the draws,
    # the rent and the refi wire later give back -- the deposit, the purchase wire, the insurance
    # bill when it is paid outside the closing, the rehab cushion (capital held, not spent) and one
    # month of utilities, hard-money interest, HOA (30 days on the same 360-day year as the holding
    # costs), insurance paid monthly and one deposit into the tax bucket.
    # The purchase wire already holds the interest prepaid from the closing day through the end
    # of that month, so the first month's interest here is the remaining days only; with no
    # closing date nothing is prepaid and the full 30 days count.
    hml_interest_first_month_days = max(0, int(DAYS_PER_MONTH) - timeline.hml_interest_days_prepaid_at_purchase_closing)
    hml_interest_first_month = calc_hml_interest(hml_amount, payload.HML_interest_rate, hml_interest_first_month_days)
    holding_costs_first_month = (calc_holding_costs(Decimal("0"), Decimal("0"), payload.montly_hoa, DAYS_PER_MONTH)
                                 + payload.monthly_insurance_until_refi + property_tax_bucket.property_tax_bucket_deposit)
    cash_needed_floor = (payload.earnest_money_deposit + buy_settlement.cash_to_close_buy + insurance.insurance_bill_at_purchase_outside_closing
                         + payload.rehab_cushion + payload.monthly_utilities_until_rented + hml_interest_first_month + holding_costs_first_month)
    # Everything spent before the refi, plus the cushion, plus the cash brought to the refi closing
    # table and the reserves the wire cannot fund if the appraisal comes in at the lowest ARV. The
    # stress test is the figure to plan around: there is no baseline variant.
    cash_needed_through_refi = (cash_out_figures.total_cash_invested + payload.rehab_cushion
                                + cash_out_figures.cash_to_refi_table_conservative
                                + cash_out_figures.reserves_funded_from_own_pocket_at_lowest_arv)
    # Cash Needed is the larger of the two. Written as a sum so the explain guard folds it exactly.
    cash_needed_floor_top_up = max(Decimal("0"), cash_needed_floor - cash_needed_through_refi)
    total_cash_needed = cash_needed_through_refi + cash_needed_floor_top_up
    return CashNeeded(
        hml_interest_first_month_days=hml_interest_first_month_days,
        hml_interest_first_month=hml_interest_first_month,
        holding_costs_first_month=holding_costs_first_month,
        cash_needed_floor=cash_needed_floor,
        cash_needed_through_refi=cash_needed_through_refi,
        cash_needed_floor_top_up=cash_needed_floor_top_up,
        total_cash_needed=total_cash_needed,
    )
