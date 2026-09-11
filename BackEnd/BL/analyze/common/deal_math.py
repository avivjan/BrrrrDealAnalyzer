"""BRRRR/Flip calculation primitives -- pure math, no persistence, no HTTP.

The one exception is `calc_mortgage_payment`, which keeps its
`raise HTTPException` verbatim (see the module docstring in `deal_validation.py`
for why: it is the zero-risk choice for a pure structural refactor).
"""

from decimal import Decimal
from typing import NamedTuple

from fastapi import HTTPException


# The 360-day banking year hard money lenders quote per-diem interest on, and
# the 30-day month it implies. Every days-driven accrual in the BRRRR calc uses
# these two, which is what makes `days = months * 30` an exact translation of
# the old month-based formulas.
DAYS_PER_YEAR = Decimal("360")
DAYS_PER_MONTH = Decimal("30")
MONTHS_PER_YEAR = Decimal("12")


def thousands_to_dollars(value: Decimal) -> Decimal:
    return value * Decimal("1000.0")

def get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab):
    return purchase_price * (1 - down_payment_precent / Decimal("100.0")) + rehab_cost * int(use_HM_for_rehab)


class OperatingExpenses(NamedTuple):
    """Monthly operating expenses of a rental, with the components spelled out."""
    total: Decimal
    vacancy: Decimal
    management: Decimal
    maintenance: Decimal
    capex: Decimal
    monthly_taxes: Decimal
    monthly_insurance: Decimal


def calc_montly_operating_expenses(payload) -> OperatingExpenses:
    vacancy = payload.rent * (payload.vacancy_percent / Decimal("100.0"))
    management = payload.rent * (payload.property_managment_fee_precentages_from_rent / Decimal("100.0"))
    maintenance = payload.rent * (payload.maintenance_percent / Decimal("100.0"))
    capex = payload.rent * (payload.capex_percent_of_rent / Decimal("100.0"))
    monthly_taxes = payload.annual_property_taxes / Decimal("12.0")
    monthly_insurance = payload.annual_insurance / Decimal("12.0")
    total = vacancy + management + maintenance + capex + monthly_taxes + monthly_insurance + payload.montly_hoa
    return OperatingExpenses(total, vacancy, management, maintenance, capex, monthly_taxes, monthly_insurance)

def calc_pitia(mortgage_payment, taxes, insurance, hoa):
    """Monthly principal + interest + taxes + insurance + association dues."""
    monthly_taxes = taxes / Decimal("12.0")
    monthly_insurance = insurance / Decimal("12.0")
    return mortgage_payment + monthly_taxes + monthly_insurance + hoa

def calcDSCR(rent, taxes, insurance, hoa, mortgage_payment):
    pitia = calc_pitia(mortgage_payment, taxes, insurance, hoa)
    if pitia == 0: return Decimal("0")
    return rent / pitia

def calc_down_payment_in_cash(down_payment_precent, purchase_price):
    return (down_payment_precent/Decimal("100")) * purchase_price

def calc_rehab_out_of_pocket(rehab_cost, use_HM_for_rehab):
    """Rehab dollars the investor pays in cash (0 when hard money funds it)."""
    return rehab_cost * (1-int(use_HM_for_rehab))

def calc_total_cash_invested(down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, use_HM_for_rehab, holding_costs_until_refi):
    """Every dollar the investor has put in before the refinance."""
    down_payment_in_cash = calc_down_payment_in_cash(down_payment_precent, purchase_price)
    return down_payment_in_cash + closing_costs_buy + HML_points_in_cash + calc_rehab_out_of_pocket(rehab_cost, use_HM_for_rehab) + HML_interest_in_cash + holding_costs_until_refi

def calc_cash_out_from_deal(arv, ltv, down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, closing_cost_refi, refi_points_in_cash, use_HM_for_rehab, holding_costs_until_refi, cash_reserve_in_cash=Decimal("0")):
    # `cash_reserve_in_cash` is committed at refi (paydown to DSCR principal),
    # so it reduces what the investor walks away with.
    cash_out_routi = calc_cash_out_routi(arv, ltv, down_payment_precent, purchase_price, rehab_cost, closing_cost_refi, refi_points_in_cash, use_HM_for_rehab, cash_reserve_in_cash)
    total_cash_invested = calc_total_cash_invested(down_payment_precent, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, use_HM_for_rehab, holding_costs_until_refi)
    return cash_out_routi - total_cash_invested


def calc_cash_out_routi(arv, ltv, down_payment_precent, purchase_price, rehab_cost, closing_cost_refi, refi_points_in_cash, use_HM_for_rehab, cash_reserve_in_cash=Decimal("0")):
    loan_amount = arv * ltv
    HML_payoff = get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    return loan_amount - HML_payoff - closing_cost_refi - refi_points_in_cash - cash_reserve_in_cash



def calc_mortgage_payment(arv, ltv, interest_rate, loan_term_years):
    loan_amount = arv * ltv
    monthly_interest_rate = (interest_rate / Decimal("100.0")) / Decimal("12.0")
    total_payments = loan_term_years * 12
    if total_payments <= 0:
        raise HTTPException(status_code=400, detail="Unable to calculate mortgage payment.")
    if monthly_interest_rate == 0:
        # A 0% loan is a straight-line principal repayment: no amortization factor.
        return loan_amount / total_payments
    factor = (1 + monthly_interest_rate) ** total_payments
    denominator = factor - 1
    if denominator == 0:
        raise HTTPException(status_code=400, detail="Unable to calculate mortgage payment.")
    return loan_amount * monthly_interest_rate * factor / denominator

def calc_cash_on_cash(cash_out_from_deal, cash_flow):
    if cash_out_from_deal >= 0: return Decimal("-1")
    elif cash_flow <= 0: return Decimal("-2")
    else: return (cash_flow * 12 / abs(cash_out_from_deal)) * Decimal("100.0")

def calc_roi(cash_out_from_deal, cash_flow, net_profit):
    if cash_out_from_deal >= 0: return Decimal("-1")
    elif cash_flow <= 0: return Decimal("-2")
    else: return ((cash_flow * 12 + net_profit )/ abs(cash_out_from_deal)) * Decimal("100.0")

def calc_holding_costs(annual_taxes, annual_insurance, monthly_hoa, days):
    """Taxes + insurance + HOA carried for `days`, accrued per diem.

    Mind the units, which the deal record mixes: taxes and insurance are
    ANNUAL figures, HOA is a MONTHLY one. So only the HOA is annualised here —
    the other two already are. (The month-based version this replaced did the
    mirror image: it divided taxes and insurance by 12 and added HOA as-is.)

    The 360-day year matches the one the HML interest accrues on, which is what
    makes a 30-day month cost exactly what the old monthly formula charged.
    Divide last: `/ 360` up front would turn an exact figure like $1,200/yr
    into a repeating Decimal and leave rounding dust in every result.
    """
    annual_holding = annual_taxes + annual_insurance + (monthly_hoa * MONTHS_PER_YEAR)
    return annual_holding * days / DAYS_PER_YEAR

def calc_HML_interest_in_cash(purchase_price, down_payment_precent, rehab_cost, days_until_refi, HML_interest_rate, use_HM_for_rehab):
    # Hard money accrues per diem: loan amount * annual rate / 360. Divide last,
    # for the same reason as above.
    HML_amount = get_HML_amount(purchase_price, down_payment_precent, rehab_cost, use_HM_for_rehab)
    return HML_amount * HML_interest_rate * days_until_refi / DAYS_PER_YEAR / Decimal("100.0")

class TotalCashNeeded(NamedTuple):
    """Lifetime cash requirement of a deal, with the buffer components spelled out.

    `rehab_cash`, `rehab_float`, `buffered_*` are the pieces the buffered total
    is made of, exposed so the explanation layer can list them without
    re-deriving the multipliers.
    """
    without_buffer: Decimal
    with_buffer: Decimal
    rehab_cash: Decimal        # rehab paid in cash (0 when hard money funds it)
    rehab_float: Decimal       # 10% of rehab kept on hand for draws/deposits
    buffered_closing: Decimal  # closing costs x 1.1
    buffered_holding: Decimal  # holding costs x 1.5
    buffered_interest: Decimal # hard-money interest x 1.5


def get_total_cash_needed_for_deal(down_payment_precent, purchase_price, holding_cost_until_refi, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, use_HM_for_rehab, refi_shortfall=Decimal("0")) -> TotalCashNeeded:
    # `refi_shortfall` is the cash the investor must bring to the refi closing
    # table when the refi loan does not cover the HML payoff + refi costs +
    # reserve (i.e. `max(0, -cash_out_routi)`). It is part of the lifetime cash
    # requirement, so it is added to both totals. Flip passes 0.
    down_payment_in_cash = calc_down_payment_in_cash(down_payment_precent, purchase_price)
    rehab_cash = calc_rehab_out_of_pocket(rehab_cost, use_HM_for_rehab)
    total_cash_needed_without_buffer = down_payment_in_cash + closing_costs_buy + HML_points_in_cash + rehab_cash + HML_interest_in_cash + holding_cost_until_refi + refi_shortfall

    # 1. Direct Rehab Cash (if not funded) + Float Buffer (for draws)
    # Even if HML pays, we need 10% on hand to start work/pay deposits
    rehab_float_buffer = Decimal("0.1") * rehab_cost

    # 2. Time Contingency (The "Safety Multiplier")
    # The x1.5 accounts for delays in permits, rehab, or tenant placement
    total_holding_cash = holding_cost_until_refi * Decimal("1.5")
    total_interest_cash = HML_interest_in_cash * Decimal("1.5")

    # 3. Closing Buffer
    total_closing_buy = closing_costs_buy * Decimal("1.1")
    # Flat, left-to-right sums in the order the explanation lists the terms
    # (BL/analyze/explain), so its guard folds them identically.
    total_cash_needed_with_buffer = down_payment_in_cash + total_closing_buy + HML_points_in_cash + rehab_cash + rehab_float_buffer + total_interest_cash + total_holding_cash + refi_shortfall
    return TotalCashNeeded(
        without_buffer=total_cash_needed_without_buffer,
        with_buffer=total_cash_needed_with_buffer,
        rehab_cash=rehab_cash,
        rehab_float=rehab_float_buffer,
        buffered_closing=total_closing_buy,
        buffered_holding=total_holding_cash,
        buffered_interest=total_interest_cash,
    )
