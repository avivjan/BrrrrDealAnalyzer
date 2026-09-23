"""BRRRR step: Cash Needed -- the single definitive out-of-pocket capital through the refi,
never below the day-one floor."""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import calc_hml_interest, calc_holding_costs, DAYS_PER_MONTH


class CashNeeded(NamedTuple):
    hml_interest_first_month: Decimal    # 30 days of the hard-money per diem
    holding_costs_first_month: Decimal   # taxes + insurance + HOA for 30 days
    cash_needed_floor: Decimal           # EMD + cash to close + cushion + one month of utilities, interest and holding costs
    cash_needed_through_refi: Decimal    # total_cash_invested + cushion + cash to the refi table at the lowest ARV
    cash_needed_floor_top_up: Decimal    # max(0, floor - through refi)
    total_cash_needed: Decimal           # max(floor, through refi), written as through refi + top-up


def total_cash_needed_step(payload, hml_amount, buy_settlement, cash_out_figures) -> CashNeeded:
    # The floor: what the deal takes on day one and through the first month whatever the draws,
    # the rent and the refi wire later give back -- the deposit, the purchase wire, the rehab
    # cushion (capital held, not spent) and one month of utilities, hard-money interest and
    # taxes, insurance and HOA (30 days on the same 360-day year as the holding costs).
    hml_interest_first_month = calc_hml_interest(hml_amount, payload.HML_interest_rate, DAYS_PER_MONTH)
    holding_costs_first_month = calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, DAYS_PER_MONTH)
    cash_needed_floor = (payload.earnest_money_deposit + buy_settlement.cash_to_close_buy + payload.rehab_cushion
                         + payload.monthly_utilities_until_rented + hml_interest_first_month + holding_costs_first_month)
    # Everything spent before the refi, plus the cushion, plus the cash brought to the refi closing
    # table if the appraisal comes in at the lowest ARV. The stress test is the figure to plan
    # around: there is no baseline variant.
    cash_needed_through_refi = (cash_out_figures.total_cash_invested + payload.rehab_cushion
                                + cash_out_figures.cash_to_refi_table_conservative)
    # Cash Needed is the larger of the two. Written as a sum so the explain guard folds it exactly.
    cash_needed_floor_top_up = max(Decimal("0"), cash_needed_floor - cash_needed_through_refi)
    total_cash_needed = cash_needed_through_refi + cash_needed_floor_top_up
    return CashNeeded(
        hml_interest_first_month=hml_interest_first_month,
        holding_costs_first_month=holding_costs_first_month,
        cash_needed_floor=cash_needed_floor,
        cash_needed_through_refi=cash_needed_through_refi,
        cash_needed_floor_top_up=cash_needed_floor_top_up,
        total_cash_needed=total_cash_needed,
    )
