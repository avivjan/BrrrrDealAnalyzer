"""BRRRR step: the hard-money payoff, everything invested before the refi, the cash-out wire
(baseline and lowest-ARV) and the net cash out."""

from decimal import Decimal
from typing import NamedTuple


class CashOut(NamedTuple):
    hml_payoff: Decimal
    total_cash_invested: Decimal
    cash_out_routi: Decimal
    cash_out_routi_conservative: Decimal
    cash_to_refi_table_conservative: Decimal
    cash_out: Decimal


def cash_out_at_refi_step(payload, hml_amount, hml, buy, rehab_cash, refi) -> CashOut:
    hml_payoff = hml_amount + hml.hml_accrued_interest_at_payoff
    # Every dollar actually spent before the refinance. EMD + cash to close is the whole
    # purchase settlement; the three interest slices are counted once each: prepaid inside
    # cash to close, monthly here, accrued inside the payoff. Rent collected offsets it.
    total_cash_invested = (payload.earnest_money_deposit + buy.cash_to_close_buy + rehab_cash
                           + hml.hml_monthly_interest_paid + hml.holding_costs + hml.utilities_until_rented
                           + payload.maintenance_before_refi + payload.appliances - hml.pre_refi_rental_income)
    cash_out_routi = (refi.refi_loan_amount - hml_payoff - refi.baseline.closing_costs_refi_total
                      - refi.baseline.prepaid_interest_refi - refi.reserves_total)
    conservative = (refi.conservative_refi_loan_amount - hml_payoff - refi.conservative.closing_costs_refi_total
                    - refi.conservative.prepaid_interest_refi - refi.reserves_total)
    cash_to_table_conservative = max(Decimal("0"), -conservative)
    cash_out = cash_out_routi - total_cash_invested
    return CashOut(hml_payoff, total_cash_invested, cash_out_routi, conservative, cash_to_table_conservative, cash_out)
