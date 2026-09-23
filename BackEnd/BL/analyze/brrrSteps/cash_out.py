"""BRRRR step: the hard-money payoff, everything invested before the refi, the cash-out wire
(baseline and lowest-ARV) and the net cash out."""

from decimal import Decimal
from typing import NamedTuple


class CashOutAtRefi(NamedTuple):
    hml_payoff: Decimal
    total_cash_invested: Decimal
    cash_out_routi: Decimal
    cash_out_routi_conservative: Decimal
    cash_to_refi_table_conservative: Decimal
    cash_out: Decimal


def cash_out_at_refi_step(payload, hml_amount, hml_and_holding, buy_settlement, rehab_paid_cash_out_of_pocket, refi_terms) -> CashOutAtRefi:
    hml_payoff = hml_amount + hml_and_holding.hml_interest_accrued_into_refi_payoff
    # Every dollar actually spent before the refinance. EMD + cash to close is the whole
    # purchase settlement; the three interest slices are counted once each: prepaid inside
    # cash to close, monthly here, accrued inside the payoff. Rent collected offsets it.
    # A positive seller tax credit came off the wire at closing but is put in the property's
    # tax bucket the day after (the buyer pays the whole year's bill in November), so it is
    # added straight back: the credit moves cash between the wire and the bucket, never out
    # of Cash Needed. A negative credit (seller already paid) is a real reimbursement and stays.
    total_cash_invested = (payload.earnest_money_deposit + buy_settlement.cash_to_close_buy
                           + buy_settlement.seller_tax_credit_set_aside_in_tax_bucket + rehab_paid_cash_out_of_pocket
                           + hml_and_holding.hml_interest_paid_monthly + hml_and_holding.holding_costs + hml_and_holding.utilities_until_rented
                           + payload.maintenance_before_refi + payload.appliances - hml_and_holding.pre_refi_rental_income)
    cash_out_routi = (refi_terms.refi_loan_amount - hml_payoff - refi_terms.at_arv.closing_costs_refi_total
                      - refi_terms.at_arv.prepaid_interest_refi - refi_terms.reserves_total)
    cash_out_routi_conservative = (refi_terms.conservative_refi_loan_amount - hml_payoff - refi_terms.at_lowest_arv.closing_costs_refi_total
                                   - refi_terms.at_lowest_arv.prepaid_interest_refi - refi_terms.reserves_total)
    cash_to_refi_table_conservative = max(Decimal("0"), -cash_out_routi_conservative)
    cash_out = cash_out_routi - total_cash_invested
    return CashOutAtRefi(
        hml_payoff=hml_payoff,
        total_cash_invested=total_cash_invested,
        cash_out_routi=cash_out_routi,
        cash_out_routi_conservative=cash_out_routi_conservative,
        cash_to_refi_table_conservative=cash_to_refi_table_conservative,
        cash_out=cash_out,
    )
