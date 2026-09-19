"""The BRRRR analysis -- the core of the product.

Three public entry points:

* `analyze_brrr` -- validate, then calculate. What `POST /analyze/brrr` calls.
* `calculate_brrr_results` -- the calculation plus its explanation, without
  validation. Also called by `BL.common.deal_response.create_deal_response`
  and by `BL.reports.reportBrrrPdf`.
* `compute_brrr_with_intermediates` -- the numbers only, as a `BrrrResultsWithIntermediates` record. No strings, no
  formatting; the thing to call for batch or high-frequency use.

`compute_brrr_with_intermediates` accepts either the Pydantic request model (`analyzeBRRRReq`)
or an ORM deal row -- everything downstream is duck-typed attribute access,
which is what lets `create_deal_response` pass a `BrrrActiveDeal` straight in.

The calculation follows the deal's lifecycle -- Buy, Rehab, Rent/Holding, Refinance -- and
is broken into named steps under `brrrSteps/`, one file per subject. Every step is pure: it
takes the already-computed values it needs and returns only the new ones. With the defaults
untouched it is a quick estimator; with the real closing date and settlement lines typed in,
Cash to Close (Buy) and the Cash-Out Wire reconcile to the settlement statements. The
narrative behind each number lives in the companion module `BL/analyze/explain/brrr.py`,
which reads the finished `BrrrResultsWithIntermediates` and never recomputes anything.
"""

from ReqRes.common.analyze_inputs import analyzeBRRRReq
from ReqRes.common.analyze_results import analyzeBRRRRes
from BL.analyze.common.validation import validate_brrr_inputs
from BL.analyze.brrr_results_with_intermediates import BrrrResultsWithIntermediates
from BL.analyze.explain.brrr import explain_brrr
from BL.analyze.brrrSteps.dollar_basis import dollar_basis_step
from BL.analyze.brrrSteps.purchase_loan import purchase_loan_step
from BL.analyze.brrrSteps.timeline import timeline_step
from BL.analyze.brrrSteps.hml_and_holding_costs import hml_and_holding_costs_step
from BL.analyze.brrrSteps.closing_costs_buy import closing_costs_buy_step
from BL.analyze.brrrSteps.rehab_draw import rehab_draw_step
from BL.analyze.brrrSteps.operating_expenses import operating_expenses_step
from BL.analyze.brrrSteps.refi_terms import refi_terms_step
from BL.analyze.brrrSteps.cash_out import cash_out_at_refi_step
from BL.analyze.brrrSteps.mortgage_payment import mortgage_payment_step
from BL.analyze.brrrSteps.cash_flow import cash_flow_step
from BL.analyze.brrrSteps.dscr import dscr_step
from BL.analyze.brrrSteps.cash_on_cash import cash_on_cash_step
from BL.analyze.brrrSteps.equity_and_net_profit import equity_and_net_profit_step
from BL.analyze.brrrSteps.roi import roi_step
from BL.analyze.brrrSteps.total_cash_needed import total_cash_needed_step


def analyze_brrr(payload: analyzeBRRRReq) -> analyzeBRRRRes:
    validate_brrr_inputs(payload)
    return calculate_brrr_results(payload)


def calculate_brrr_results(payload) -> analyzeBRRRRes:
    """Numbers plus their explanation, as the API response model."""
    r = compute_brrr_with_intermediates(payload)
    return analyzeBRRRRes(
        cash_flow=r.cash_flow, dscr=r.dscr, cash_out=r.cash_out,
        cash_out_routi=r.cash_out_routi, cash_out_routi_conservative=r.cash_out_routi_conservative,
        cash_to_refi_table_conservative=r.cash_to_refi_table_conservative,
        cash_on_cash=r.cash_on_cash, roi=r.roi, equity=r.equity, net_profit=r.net_profit,
        total_cash_needed_for_deal=r.total_cash_needed, cash_needed_conservative=r.cash_needed_conservative,
        total_cash_invested=r.total_cash_invested, cash_to_close_buy=r.cash_to_close_buy,
        purchase_loan_amount=r.purchase_loan_amount, hml_amount=r.hml_amount, hml_payoff=r.hml_payoff,
        total_hard_money_cost=r.total_hard_money_cost, prepaid_interest_buy=r.prepaid_interest_buy,
        seller_tax_credit=r.seller_tax_credit, closing_costs_buy_total=r.closing_costs_buy_total,
        stolen_money=r.stolen_money, pre_refi_rental_income=r.pre_refi_rental_income,
        closing_costs_refi_total=r.closing_costs_refi_total, prepaid_interest_refi=r.prepaid_interest_refi,
        reserves_total=r.reserves_total,
        refi_closing_date=r.refi_closing_date, tenant_occupied_date=r.tenant_occupied_date,
        recording_transfer_buy_effective=r.recording_transfer_buy, title_escrow_buy_effective=r.title_escrow_buy,
        recording_transfer_refi_effective=r.recording_transfer_refi, title_escrow_refi_effective=r.title_escrow_refi,
        vacancy_reserve_effective=r.vacancy_reserve, lowest_arv_effective=r.lowest_arv,
        messages=None,
        breakdowns=explain_brrr(payload, r),
    )


def compute_brrr_with_intermediates(payload) -> BrrrResultsWithIntermediates:
    """Run every BRRRR step in lifecycle order. Reading top to bottom is reading the calculation."""
    # Buy
    arv, purchase_price, rehab_cost_base, rehab_contingency, rehab_cost, construction_budget, lowest_arv = dollar_basis_step(payload)
    purchase_loan_amount, down_payment_cash, hml_amount = purchase_loan_step(payload, purchase_price, construction_budget)
    timeline = timeline_step(payload)
    hml = hml_and_holding_costs_step(payload, hml_amount, timeline)
    buy = closing_costs_buy_step(payload, purchase_price, purchase_loan_amount, down_payment_cash, hml, timeline)
    # Rehab
    stolen_money, rehab_cash = rehab_draw_step(rehab_cost, construction_budget)
    # Rent
    opex = operating_expenses_step(payload)
    # Refinance
    refi = refi_terms_step(payload, arv, lowest_arv, timeline)
    cash = cash_out_at_refi_step(payload, hml_amount, hml, buy, rehab_cash, refi)
    mortgage_payment = mortgage_payment_step(payload, arv, refi.ltv)
    net_operating_income, cash_flow = cash_flow_step(payload, opex.total, mortgage_payment)
    pitia, dscr = dscr_step(payload, mortgage_payment)
    cash_on_cash = cash_on_cash_step(cash.cash_out, cash_flow)
    equity, net_profit = equity_and_net_profit_step(arv, refi.ltv, refi.reserves_total, cash.cash_out)
    roi = roi_step(cash.cash_out, cash_flow, net_profit)
    refi_shortfall, total_cash_needed, cash_needed_conservative = total_cash_needed_step(payload, cash)

    return BrrrResultsWithIntermediates(
        arv=arv, lowest_arv=lowest_arv, purchase_price=purchase_price, rehab_cost_base=rehab_cost_base,
        rehab_contingency=rehab_contingency, rehab_cost=rehab_cost, construction_budget=construction_budget,
        purchase_loan_amount=purchase_loan_amount, down_payment_cash=down_payment_cash, hml_amount=hml_amount,
        buy_closing_date=timeline.buy_closing_date, refi_closing_date=timeline.refi_closing_date,
        tenant_occupied_date=timeline.tenant_occupied_date, prepaid_days_buy=timeline.prepaid_days_buy,
        monthly_interest_days=timeline.monthly_interest_days, accrued_days_at_payoff=timeline.accrued_days_at_payoff,
        prepaid_days_refi=timeline.prepaid_days_refi, days_rented_before_refi=timeline.days_rented_before_refi,
        hml_points=hml.hml_points, hml_per_diem=hml.hml_per_diem, hml_interest=hml.hml_interest,
        prepaid_interest_buy=hml.prepaid_interest_buy, hml_monthly_interest_paid=hml.hml_monthly_interest_paid,
        hml_accrued_interest_at_payoff=hml.hml_accrued_interest_at_payoff, holding_costs=hml.holding_costs,
        utilities_until_rented=hml.utilities_until_rented, pre_refi_rental_income=hml.pre_refi_rental_income,
        recording_transfer_buy=buy.recording_transfer_buy, title_escrow_buy=buy.title_escrow_buy, notary_buy=buy.notary_buy,
        closing_costs_buy_total=buy.closing_costs_buy_total, seller_paid_current_year_taxes=buy.seller_paid_current_year_taxes,
        seller_tax_credit=buy.seller_tax_credit, cash_to_close_buy=buy.cash_to_close_buy,
        total_hard_money_cost=buy.total_hard_money_cost,
        stolen_money=stolen_money, rehab_cash=rehab_cash,
        ltv=refi.ltv, refi_loan_amount=refi.refi_loan_amount, conservative_refi_loan_amount=refi.conservative_refi_loan_amount,
        broker_points_refi=refi.baseline.broker_points_refi, broker_points_refi_conservative=refi.conservative.broker_points_refi,
        recording_transfer_refi=refi.baseline.recording_transfer_refi, recording_transfer_refi_conservative=refi.conservative.recording_transfer_refi,
        title_escrow_refi=refi.baseline.title_escrow_refi, title_escrow_refi_conservative=refi.conservative.title_escrow_refi,
        notary_refi=refi.notary_refi, closing_costs_refi_total=refi.baseline.closing_costs_refi_total,
        closing_costs_refi_total_conservative=refi.conservative.closing_costs_refi_total,
        prepaid_interest_refi=refi.baseline.prepaid_interest_refi, prepaid_interest_refi_conservative=refi.conservative.prepaid_interest_refi,
        vacancy_reserve=refi.vacancy_reserve, reserves_total=refi.reserves_total,
        hml_payoff=cash.hml_payoff, total_cash_invested=cash.total_cash_invested, cash_out_routi=cash.cash_out_routi,
        cash_out_routi_conservative=cash.cash_out_routi_conservative,
        cash_to_refi_table_conservative=cash.cash_to_refi_table_conservative, cash_out=cash.cash_out,
        vacancy=opex.vacancy, management_fee=opex.management, maintenance=opex.maintenance, capex=opex.capex,
        monthly_taxes=opex.monthly_taxes, monthly_insurance=opex.monthly_insurance,
        operating_expenses=opex.total, mortgage_payment=mortgage_payment,
        net_operating_income=net_operating_income, cash_flow=cash_flow, pitia=pitia, dscr=dscr,
        cash_on_cash=cash_on_cash, equity=equity, net_profit=net_profit, roi=roi,
        refi_shortfall=refi_shortfall, total_cash_needed=total_cash_needed, cash_needed_conservative=cash_needed_conservative,
    )
