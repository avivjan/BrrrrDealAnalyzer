"""BRRRR step: the hard-money payoff, everything invested before the refi, the cash-out wire
(baseline and lowest-ARV) and the net cash out."""

from decimal import Decimal
from typing import NamedTuple


class CashOutAtRefi(NamedTuple):
    hml_payoff: Decimal
    appraisal_and_survey_paid_outside_closing: Decimal
    total_cash_invested: Decimal
    cash_out_routi: Decimal
    cash_out_routi_conservative: Decimal
    cash_to_refi_table_conservative: Decimal
    reserves_funded_from_own_pocket_at_lowest_arv: Decimal
    cash_out: Decimal


def cash_out_at_refi_step(payload, hml_amount, hml_and_holding, buy_settlement, rehab_paid_cash_out_of_pocket, refi_terms,
                          insurance, property_tax_bucket) -> CashOutAtRefi:
    hml_payoff = hml_amount + hml_and_holding.hml_interest_accrued_into_refi_payoff
    # Paid outside the refi closing at the end of the rehab (POC on the refi settlement statement).
    appraisal_and_survey_paid_outside_closing = payload.appraisal_fee + payload.survey_fee
    # Every dollar actually spent before the refinance. EMD + cash to close is the whole
    # purchase settlement; the three interest slices are counted once each: prepaid inside
    # cash to close, monthly here, accrued inside the payoff. Rent collected offsets it.
    # A positive seller tax credit came off the wire at closing but is put in the property's
    # tax bucket the day after (the buyer pays the whole year's bill in November), so it is
    # added straight back: the credit moves cash between the wire and the bucket, never out
    # of Cash Needed. A negative credit (seller already paid) is a real reimbursement and stays.
    # The tax deposits into the bucket are real spending; when the refi lender collects the
    # whole bill, the bucket's balance comes back and is taken off again.
    total_cash_invested = (payload.earnest_money_deposit + buy_settlement.cash_to_close_buy
                           + buy_settlement.seller_tax_credit_set_aside_in_tax_bucket + insurance.insurance_bill_at_purchase_outside_closing
                           + rehab_paid_cash_out_of_pocket + hml_and_holding.hml_interest_paid_monthly + hml_and_holding.hoa_dues_until_refi
                           + insurance.insurance_paid_monthly_until_refi + property_tax_bucket.property_tax_paid_into_bucket_until_refi
                           + property_tax_bucket.property_tax_bucket_shortfall_topped_up_on_november_30
                           + hml_and_holding.utilities_until_rented + payload.maintenance_before_refi + payload.appliances
                           + appraisal_and_survey_paid_outside_closing + insurance.insurance_bill_at_refi_outside_closing
                           - hml_and_holding.pre_refi_rental_income - property_tax_bucket.property_tax_bucket_balance_released_at_refi)
    # The wires are the "Due to Borrower" lines of the refi settlement statement: the reserves
    # are the owner's own money set aside afterwards, never a settlement line.
    cash_out_routi = (refi_terms.refi_loan_amount - hml_payoff - refi_terms.at_arv.closing_costs_refi_total
                      - refi_terms.at_arv.prepaid_interest_refi)
    cash_out_routi_conservative = (refi_terms.conservative_refi_loan_amount - hml_payoff - refi_terms.at_lowest_arv.closing_costs_refi_total
                                   - refi_terms.at_lowest_arv.prepaid_interest_refi)
    cash_to_refi_table_conservative = max(Decimal("0"), -cash_out_routi_conservative)
    # The reserves the lowest-ARV wire cannot fund come out of pocket, so Cash Needed carries them.
    reserves_funded_from_own_pocket_at_lowest_arv = max(Decimal("0"), refi_terms.reserves_total - max(Decimal("0"), cash_out_routi_conservative))
    # The reserves stay in the deal: they lower the cash out (and count as equity).
    cash_out = cash_out_routi - refi_terms.reserves_total - total_cash_invested
    return CashOutAtRefi(
        hml_payoff=hml_payoff,
        appraisal_and_survey_paid_outside_closing=appraisal_and_survey_paid_outside_closing,
        total_cash_invested=total_cash_invested,
        cash_out_routi=cash_out_routi,
        cash_out_routi_conservative=cash_out_routi_conservative,
        cash_to_refi_table_conservative=cash_to_refi_table_conservative,
        reserves_funded_from_own_pocket_at_lowest_arv=reserves_funded_from_own_pocket_at_lowest_arv,
        cash_out=cash_out,
    )
