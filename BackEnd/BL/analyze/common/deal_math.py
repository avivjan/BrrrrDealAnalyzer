"""BRRRR/Flip calculation primitives -- pure math, no persistence, no HTTP.

The one exception is `calc_mortgage_payment`, which keeps its
`raise HTTPException` verbatim (see the module docstring in `deal_validation.py`
for why: it is the zero-risk choice for a pure structural refactor).
"""

import calendar
from datetime import date
from decimal import Decimal
from typing import NamedTuple, Optional

from fastapi import HTTPException


# The 360-day banking year hard money lenders quote per-diem interest on, and
# the 30-day month it implies. Every days-driven accrual in the BRRRR calc uses
# these two, which is what makes `days = months * 30` an exact translation of
# the old month-based formulas.
DAYS_PER_YEAR = Decimal("360")
DAYS_PER_MONTH = Decimal("30")
MONTHS_PER_YEAR = Decimal("12")

# The DSCR (refinance) loan quotes per-diem interest on a calendar year, as the
# Closing Disclosure does; hard money keeps the 360-day banking year above.
DSCR_DAYS_PER_YEAR = Decimal("365")

# Fixed fees and formula defaults of the BRRRR settlement lines. A `None` input on
# the matching field means "use the formula"; see ReqRes/common/brrr_lifecycle_inputs.py.
ONLINE_NOTARY_FEE = Decimal("250")
RECORDING_TRANSFER_RATE = Decimal("0.0055")   # of the loan recorded (0.35% + 0.20%)
RECORDING_TRANSFER_FLAT = Decimal("250")      # deed, mortgage and LLC affidavit recording
DEED_TRANSFER_TAX_RATE_WE_PAY_ALL = Decimal("0.0070")   # of the purchase price, only when we pay all closing costs
TITLE_ESCROW_BUY_STANDARD = Decimal("1000")   # lender's policy + endorsements + settlement/search
TITLE_ESCROW_BUY_WE_PAY_ALL = (               # (upper price bound, flat fee) when the buyer pays all title charges
    (Decimal("150000"), Decimal("2050")),
    (Decimal("200000"), Decimal("2200")),
)
TITLE_ESCROW_BUY_WE_PAY_ALL_TOP = Decimal("2400")
TITLE_ESCROW_REFI_FLAT = Decimal("800")
TITLE_ESCROW_REFI_RATE = Decimal("0.0045")
LOWEST_ARV_FACTOR = Decimal("0.90")


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

def calc_hml_interest(hml_amount, HML_interest_rate, days):
    """Hard-money interest over `days`: amount x annual rate / 360, per diem. Divide last (see above)."""
    return hml_amount * HML_interest_rate * Decimal(days) / DAYS_PER_YEAR / Decimal("100.0")

def calc_prepaid_interest_refi(loan_amount, interest_rate, days):
    """DSCR-loan per-diem interest over `days` on a 365-day year. Divide last."""
    return loan_amount * interest_rate * Decimal(days) / DSCR_DAYS_PER_YEAR / Decimal("100.0")


# -- settlement-line helpers (BRRRR lifecycle) ----------------------------------

def effective(user_value, formula_default):
    """The user's value, or the formula default when the field was left `None`."""
    return formula_default if user_value is None else user_value

def days_in_month(day: date) -> int:
    return calendar.monthrange(day.year, day.month)[1]

def days_in_year(day: date) -> int:
    return 366 if calendar.isleap(day.year) else 365

def days_through_month_end(day: date) -> int:
    """Days from `day` through the last day of its month, both inclusive (the prepaid-interest window)."""
    return days_in_month(day) - day.day + 1

def calc_seller_tax_credit(annual_taxes, closing_date: date, seller_already_paid_current_year_taxes: bool):
    """Property-tax proration on the purchase settlement, positive = credit to the buyer.

    Taxes are billed in November for the calendar year. Until then the seller owes the
    buyer for the days they owned (Jan 1 to the day before closing), because the buyer will
    pay the whole bill. Once the seller has paid the bill (a December closing by default)
    it reverses: the buyer owes the seller for closing day through Dec 31.
    Calendar-day proration on the closing year's 365 or 366 days, divide last.
    """
    days_in_closing_year = days_in_year(closing_date)
    closing_day_of_year = closing_date.timetuple().tm_yday
    if seller_already_paid_current_year_taxes:
        return -annual_taxes * Decimal(days_in_closing_year - closing_day_of_year + 1) / Decimal(days_in_closing_year)
    return annual_taxes * Decimal(closing_day_of_year - 1) / Decimal(days_in_closing_year)

def recording_transfer_default(loan_amount):
    """Government recording & transfer charges at refi: 0.55% of the loan recorded + $250."""
    return RECORDING_TRANSFER_RATE * loan_amount + RECORDING_TRANSFER_FLAT

def deed_transfer_tax_buy_default(title_mode: str, purchase_price):
    """Deed transfer tax at purchase: the seller's debit on a standard deal ($0); 0.70% of the
    purchase price when we pay all closing costs."""
    return DEED_TRANSFER_TAX_RATE_WE_PAY_ALL * purchase_price if title_mode == "we_pay_all" else Decimal("0")

def recording_transfer_buy_default(hml_amount, deed_transfer_tax):
    """Government recording & transfer charges at purchase: $250 + 0.55% of the WHOLE hard-money
    loan (purchase loan + construction budget, the mortgage recorded) + the deed transfer tax."""
    return RECORDING_TRANSFER_FLAT + RECORDING_TRANSFER_RATE * hml_amount + deed_transfer_tax

def title_escrow_buy_default(title_mode: str, purchase_price):
    """Title/escrow/settlement at purchase: $1,000 standard, or the we-pay-all tier by price
    ($2,050 under $150k, $2,200 from $150k to $200k inclusive, $2,400 above)."""
    if title_mode != "we_pay_all":
        return TITLE_ESCROW_BUY_STANDARD
    for price_upper_bound, title_fee in TITLE_ESCROW_BUY_WE_PAY_ALL:
        if purchase_price < price_upper_bound:
            return title_fee
    if purchase_price == TITLE_ESCROW_BUY_WE_PAY_ALL[-1][0]:
        return TITLE_ESCROW_BUY_WE_PAY_ALL[-1][1]
    return TITLE_ESCROW_BUY_WE_PAY_ALL_TOP

def title_escrow_refi_default(loan_amount):
    """Title/escrow/settlement at refi: $800 + 0.45% of the refi loan."""
    return TITLE_ESCROW_REFI_FLAT + TITLE_ESCROW_REFI_RATE * loan_amount

def lowest_arv_default(arv):
    return LOWEST_ARV_FACTOR * arv

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
