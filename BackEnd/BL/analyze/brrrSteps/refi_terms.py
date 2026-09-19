"""BRRRR step: the refinance settlement -- loan, closing-cost lines, prepaid interest, reserves --
at the baseline ARV and again at the lowest ARV (the stress test)."""

from decimal import Decimal
from typing import NamedTuple

from BL.analyze.common.deal_math import (
    effective, recording_transfer_default, title_escrow_refi_default, calc_prepaid_interest_refi, ONLINE_NOTARY_FEE,
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
    baseline: RefiSettlementLines
    conservative: RefiSettlementLines
    vacancy_reserve: Decimal           # effective
    reserves_total: Decimal


def _settlement_lines(payload, loan_amount, notary, prepaid_days) -> RefiSettlementLines:
    broker_points = payload.refi_points / Decimal("100") * loan_amount
    recording = effective(payload.recording_transfer_refi, recording_transfer_default(loan_amount))
    title = effective(payload.title_escrow_refi, title_escrow_refi_default(loan_amount))
    total = (payload.loan_charges_refi + recording + title + notary + payload.appraisal_fee + payload.survey_fee
             + payload.refi_underwriting_fee + broker_points + payload.broker_processing_fee_refi
             + payload.other_closing_costs_refi)
    prepaid = calc_prepaid_interest_refi(loan_amount, payload.interest_rate, prepaid_days)
    return RefiSettlementLines(broker_points, recording, title, total, prepaid)


def refi_terms_step(payload, arv, lowest_arv, timeline) -> RefiTerms:
    ltv = payload.ltv_as_precent / Decimal("100")
    refi_loan_amount = arv * ltv
    conservative_loan = lowest_arv * ltv
    notary = ONLINE_NOTARY_FEE if payload.online_notary_refi else Decimal("0")
    baseline = _settlement_lines(payload, refi_loan_amount, notary, timeline.prepaid_days_refi)
    conservative = _settlement_lines(payload, conservative_loan, notary, timeline.prepaid_days_refi)
    vacancy_reserve = effective(payload.vacancy_reserve, payload.rent)
    reserves_total = payload.maintenance_reserve + vacancy_reserve + payload.capex_reserve
    return RefiTerms(ltv, refi_loan_amount, conservative_loan, notary, baseline, conservative, vacancy_reserve, reserves_total)
