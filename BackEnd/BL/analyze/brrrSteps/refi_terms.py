"""BRRRR step: the refinance settlement -- loan, closing-cost lines (the insurance bill and the tax
lump when the lender collects them), prepaid interest -- at the baseline ARV and again at the lowest
ARV (the stress test), and the reserves the owner sets aside at the refi.

The appraisal and the survey are paid outside the refi closing at the end of the rehab, so they are
not settlement lines (`cash_out.py` counts them in Total Cash Invested). The reserves are the owner's
own money, not the lender's escrow: they never come off the wire."""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import (
    effective, recording_transfer_default, title_escrow_refi_default, calc_prepaid_interest_refi, ONLINE_NOTARY_FEE,
    HYSA_DEPOSIT_MONTHS_OF_PRINCIPAL_AND_INTEREST,
)


class RefiSettlementLines(NamedTuple):
    broker_points_refi: Decimal
    recording_transfer_refi: Decimal   # effective
    title_escrow_refi: Decimal         # effective
    closing_costs_refi_total: Decimal
    prepaid_interest_refi: Decimal


class RefiTerms(NamedTuple):
    ltv: Decimal
    refi_loan_amount: Decimal
    conservative_refi_loan_amount: Decimal
    notary_refi: Decimal
    at_arv: RefiSettlementLines          # the settlement at the baseline ARV
    at_lowest_arv: RefiSettlementLines   # the same settlement at the lowest ARV (stress test)
    vacancy_reserve: Decimal             # effective
    hysa_deposit_at_refi: Decimal        # effective: input or 3 months of principal and interest
    reserves_total: Decimal              # maintenance + vacancy + capex + HYSA; set aside by the owner


def ltv_as_fraction(payload) -> Decimal:
    return payload.ltv_as_precent / Decimal("100")


def _refi_settlement_lines(payload, refi_loan_amount, notary_refi, dscr_interest_days_prepaid_at_refi_closing,
                           insurance_bill_at_refi_inside_closing, property_tax_lump_sum_at_refi_closing) -> RefiSettlementLines:
    broker_points_refi = payload.refi_points / Decimal("100") * refi_loan_amount
    recording_transfer_refi = effective(payload.recording_transfer_refi, recording_transfer_default(refi_loan_amount))
    title_escrow_refi = effective(payload.title_escrow_refi, title_escrow_refi_default(refi_loan_amount))
    closing_costs_refi_total = (payload.loan_charges_refi + recording_transfer_refi + title_escrow_refi + notary_refi
                                + payload.refi_underwriting_fee + broker_points_refi + payload.broker_processing_fee_refi
                                + payload.other_closing_costs_refi + insurance_bill_at_refi_inside_closing
                                + property_tax_lump_sum_at_refi_closing)
    prepaid_interest_refi = calc_prepaid_interest_refi(refi_loan_amount, payload.interest_rate, dscr_interest_days_prepaid_at_refi_closing)
    return RefiSettlementLines(
        broker_points_refi=broker_points_refi,
        recording_transfer_refi=recording_transfer_refi,
        title_escrow_refi=title_escrow_refi,
        closing_costs_refi_total=closing_costs_refi_total,
        prepaid_interest_refi=prepaid_interest_refi,
    )


def refi_terms_step(payload, arv, lowest_arv, timeline, insurance, property_tax_bucket, mortgage_payment) -> RefiTerms:
    ltv = ltv_as_fraction(payload)
    refi_loan_amount = arv * ltv
    conservative_refi_loan_amount = lowest_arv * ltv
    notary_refi = effective(payload.online_notary_fee_refi, ONLINE_NOTARY_FEE) if payload.online_notary_refi else Decimal("0")
    settlement_lines_independent_of_the_loan = (notary_refi, timeline.dscr_interest_days_prepaid_at_refi_closing,
                                                insurance.insurance_bill_at_refi_inside_closing,
                                                property_tax_bucket.property_tax_lump_sum_at_refi_closing)
    settlement_at_arv = _refi_settlement_lines(payload, refi_loan_amount, *settlement_lines_independent_of_the_loan)
    settlement_at_lowest_arv = _refi_settlement_lines(payload, conservative_refi_loan_amount, *settlement_lines_independent_of_the_loan)
    vacancy_reserve = effective(payload.vacancy_reserve, payload.rent)
    hysa_deposit_at_refi = effective(payload.hysa_deposit_at_refi, HYSA_DEPOSIT_MONTHS_OF_PRINCIPAL_AND_INTEREST * mortgage_payment)
    reserves_total = payload.maintenance_reserve + vacancy_reserve + payload.capex_reserve + hysa_deposit_at_refi
    return RefiTerms(
        ltv=ltv,
        refi_loan_amount=refi_loan_amount,
        conservative_refi_loan_amount=conservative_refi_loan_amount,
        notary_refi=notary_refi,
        at_arv=settlement_at_arv,
        at_lowest_arv=settlement_at_lowest_arv,
        vacancy_reserve=vacancy_reserve,
        hysa_deposit_at_refi=hysa_deposit_at_refi,
        reserves_total=reserves_total,
    )
