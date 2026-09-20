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
    results = compute_brrr_with_intermediates(payload)
    return analyzeBRRRRes(
        cash_flow=results.cash_flow, dscr=results.dscr, cash_out=results.cash_out,
        cash_out_routi=results.cash_out_routi, cash_out_routi_conservative=results.cash_out_routi_conservative,
        cash_to_refi_table_conservative=results.cash_to_refi_table_conservative,
        cash_on_cash=results.cash_on_cash, roi=results.roi, equity=results.equity, net_profit=results.net_profit,
        total_cash_needed_for_deal=results.total_cash_needed,
        total_cash_invested=results.total_cash_invested, cash_to_close_buy=results.cash_to_close_buy,
        purchase_loan_amount=results.purchase_loan_amount, hml_amount=results.hml_amount, hml_payoff=results.hml_payoff,
        total_hard_money_cost=results.total_hard_money_cost, prepaid_interest_buy=results.prepaid_interest_buy,
        seller_tax_credit=results.seller_tax_credit, closing_costs_buy_total=results.closing_costs_buy_total,
        deed_transfer_tax_buy=results.deed_transfer_tax_buy,
        stolen_money=results.stolen_money, pre_refi_rental_income=results.pre_refi_rental_income,
        closing_costs_refi_total=results.closing_costs_refi_total, prepaid_interest_refi=results.prepaid_interest_refi,
        reserves_total=results.reserves_total,
        refi_closing_date=results.refi_closing_date, tenant_occupied_date=results.tenant_occupied_date,
        recording_transfer_buy_effective=results.recording_transfer_buy, title_escrow_buy_effective=results.title_escrow_buy,
        recording_transfer_refi_effective=results.recording_transfer_refi, title_escrow_refi_effective=results.title_escrow_refi,
        vacancy_reserve_effective=results.vacancy_reserve, lowest_arv_effective=results.lowest_arv,
        messages=None,
        breakdowns=explain_brrr(payload, results),
    )


def compute_brrr_with_intermediates(payload) -> BrrrResultsWithIntermediates:
    """Run every BRRRR step in lifecycle order. Reading top to bottom is reading the calculation."""
    # Buy
    arv, purchase_price, rehab_cost_base, rehab_contingency, rehab_cost, construction_budget, lowest_arv = dollar_basis_step(payload)
    purchase_loan_amount, down_payment_cash, hml_amount = purchase_loan_step(payload, purchase_price, construction_budget)
    timeline = timeline_step(payload)
    hml_and_holding = hml_and_holding_costs_step(payload, hml_amount, timeline)
    buy_settlement = closing_costs_buy_step(payload, purchase_price, hml_amount, down_payment_cash, hml_and_holding, timeline)
    # Rehab
    stolen_money, rehab_paid_cash_out_of_pocket = rehab_draw_step(rehab_cost, construction_budget)
    # Rent
    operating_expenses = operating_expenses_step(payload)
    # Refinance
    refi_terms = refi_terms_step(payload, arv, lowest_arv, timeline)
    cash_out_figures = cash_out_at_refi_step(payload, hml_amount, hml_and_holding, buy_settlement, rehab_paid_cash_out_of_pocket, refi_terms)
    mortgage_payment = mortgage_payment_step(payload, arv, refi_terms.ltv)
    net_operating_income, cash_flow = cash_flow_step(payload, operating_expenses.total, mortgage_payment)
    pitia, dscr = dscr_step(payload, mortgage_payment)
    cash_on_cash = cash_on_cash_step(cash_out_figures.cash_out, cash_flow)
    equity, net_profit = equity_and_net_profit_step(arv, refi_terms.ltv, refi_terms.reserves_total, cash_out_figures.cash_out)
    roi = roi_step(cash_out_figures.cash_out, cash_flow, net_profit)
    total_cash_needed = total_cash_needed_step(payload, cash_out_figures)

    return BrrrResultsWithIntermediates(
        arv=arv, lowest_arv=lowest_arv, purchase_price=purchase_price, rehab_cost_base=rehab_cost_base,
        rehab_contingency=rehab_contingency, rehab_cost=rehab_cost, construction_budget=construction_budget,
        purchase_loan_amount=purchase_loan_amount, down_payment_cash=down_payment_cash, hml_amount=hml_amount,
        buy_closing_date=timeline.buy_closing_date, refi_closing_date=timeline.refi_closing_date,
        tenant_occupied_date=timeline.tenant_occupied_date, hml_interest_days_prepaid_at_purchase_closing=timeline.hml_interest_days_prepaid_at_purchase_closing,
        hml_interest_days_paid_monthly=timeline.hml_interest_days_paid_monthly, hml_interest_days_accrued_into_refi_payoff=timeline.hml_interest_days_accrued_into_refi_payoff,
        dscr_interest_days_prepaid_at_refi_closing=timeline.dscr_interest_days_prepaid_at_refi_closing, days_tenant_occupied_before_refi=timeline.days_tenant_occupied_before_refi,
        hml_points=hml_and_holding.hml_points, hml_per_diem=hml_and_holding.hml_per_diem, hml_interest=hml_and_holding.hml_interest,
        prepaid_interest_buy=hml_and_holding.prepaid_interest_buy, hml_interest_paid_monthly=hml_and_holding.hml_interest_paid_monthly,
        hml_interest_accrued_into_refi_payoff=hml_and_holding.hml_interest_accrued_into_refi_payoff, holding_costs=hml_and_holding.holding_costs,
        utilities_until_rented=hml_and_holding.utilities_until_rented, pre_refi_rental_income=hml_and_holding.pre_refi_rental_income,
        deed_transfer_tax_buy=buy_settlement.deed_transfer_tax_buy,
        recording_transfer_buy=buy_settlement.recording_transfer_buy, title_escrow_buy=buy_settlement.title_escrow_buy, notary_buy=buy_settlement.notary_buy,
        closing_costs_buy_total=buy_settlement.closing_costs_buy_total, seller_paid_current_year_taxes=buy_settlement.seller_paid_current_year_taxes,
        seller_tax_credit=buy_settlement.seller_tax_credit, cash_to_close_buy=buy_settlement.cash_to_close_buy,
        total_hard_money_cost=buy_settlement.total_hard_money_cost,
        stolen_money=stolen_money, rehab_paid_cash_out_of_pocket=rehab_paid_cash_out_of_pocket,
        ltv=refi_terms.ltv, refi_loan_amount=refi_terms.refi_loan_amount, conservative_refi_loan_amount=refi_terms.conservative_refi_loan_amount,
        broker_points_refi=refi_terms.at_arv.broker_points_refi, broker_points_refi_conservative=refi_terms.at_lowest_arv.broker_points_refi,
        recording_transfer_refi=refi_terms.at_arv.recording_transfer_refi, recording_transfer_refi_conservative=refi_terms.at_lowest_arv.recording_transfer_refi,
        title_escrow_refi=refi_terms.at_arv.title_escrow_refi, title_escrow_refi_conservative=refi_terms.at_lowest_arv.title_escrow_refi,
        notary_refi=refi_terms.notary_refi, closing_costs_refi_total=refi_terms.at_arv.closing_costs_refi_total,
        closing_costs_refi_total_conservative=refi_terms.at_lowest_arv.closing_costs_refi_total,
        prepaid_interest_refi=refi_terms.at_arv.prepaid_interest_refi, prepaid_interest_refi_conservative=refi_terms.at_lowest_arv.prepaid_interest_refi,
        vacancy_reserve=refi_terms.vacancy_reserve, reserves_total=refi_terms.reserves_total,
        hml_payoff=cash_out_figures.hml_payoff, total_cash_invested=cash_out_figures.total_cash_invested, cash_out_routi=cash_out_figures.cash_out_routi,
        cash_out_routi_conservative=cash_out_figures.cash_out_routi_conservative,
        cash_to_refi_table_conservative=cash_out_figures.cash_to_refi_table_conservative, cash_out=cash_out_figures.cash_out,
        vacancy=operating_expenses.vacancy, management_fee=operating_expenses.management, maintenance=operating_expenses.maintenance, capex=operating_expenses.capex,
        monthly_taxes=operating_expenses.monthly_taxes, monthly_insurance=operating_expenses.monthly_insurance,
        operating_expenses=operating_expenses.total, mortgage_payment=mortgage_payment,
        net_operating_income=net_operating_income, cash_flow=cash_flow, pitia=pitia, dscr=dscr,
        cash_on_cash=cash_on_cash, equity=equity, net_profit=net_profit, roi=roi,
        total_cash_needed=total_cash_needed,
    )
