"""The Flip analysis -- the core of the product.

Three public entry points:

* `analyze_flip` -- validate, then calculate. What `POST /analyze/flip` calls.
* `calculate_flip_results` -- the calculation plus its explanation, without
  validation. Also called by `BL.common.deal_response.create_deal_response`
  and by `BL.reports.reportFlipPdf`.
* `compute_flip_with_intermediates` -- the numbers only, as a `FlipResultsWithIntermediates` record. No strings, no
  formatting; the thing to call for batch or high-frequency use.

`compute_flip_with_intermediates` accepts either the Pydantic request model (`analyzeFlipReq`)
or an ORM deal row -- everything downstream is duck-typed attribute access,
which is what lets `create_deal_response` pass a `FlipActiveDeal` straight in.

The calculation is broken into named steps under `flipSteps/`, one file per
subject. Every step is pure: it takes the already-computed values it needs
and returns only the new ones. The narrative behind each number lives in the
companion module `BL/analyze/explain/flip.py`, which reads the finished
`FlipResultsWithIntermediates` and never recomputes anything.
"""

from ReqRes.common.analyze_inputs import analyzeFlipReq
from ReqRes.common.analyze_results import analyzeFlipRes
from BL.analyze.common.validation import validate_flip_inputs
from BL.analyze.flip_results_with_intermediates import FlipResultsWithIntermediates
from BL.analyze.explain.flip import explain_flip
from BL.analyze.flipSteps.dollar_basis import dollar_basis_and_rehab_cost_step
from BL.analyze.flipSteps.hml_costs import hml_costs_step
from BL.analyze.flipSteps.holding_costs import operating_and_holding_costs_step
from BL.analyze.flipSteps.selling_costs import selling_costs_step
from BL.analyze.flipSteps.total_cash_needed import total_cash_needed_step
from BL.analyze.flipSteps.cost_basis import cash_invested_and_cost_basis_step
from BL.analyze.flipSteps.net_profit import net_profit_after_tax_step
from BL.analyze.flipSteps.roi import roi_and_annualized_step


def analyze_flip(payload: analyzeFlipReq) -> analyzeFlipRes:
    validate_flip_inputs(payload)
    return calculate_flip_results(payload)


def calculate_flip_results(payload) -> analyzeFlipRes:
    """Numbers plus their explanation, as the API response model."""
    results_w_intermediates = compute_flip_with_intermediates(payload)
    return analyzeFlipRes(
        net_profit=results_w_intermediates.net_profit, roi=results_w_intermediates.roi, annualized_roi=results_w_intermediates.annualized_roi,
        total_cash_needed=results_w_intermediates.total_cash_needed,
        total_cash_needed_with_buffer=results_w_intermediates.total_cash_needed_with_buffer,
        total_holding_costs=results_w_intermediates.total_holding_costs,
        total_hml_interest=results_w_intermediates.total_hml_interest, messages=[],
        breakdowns=explain_flip(payload, results_w_intermediates),
    )


def compute_flip_with_intermediates(payload) -> FlipResultsWithIntermediates:
    """Run every Flip results_w_intermediates step in order. Reading top to bottom is reading the calculation."""
    purchase_price, sale_price, closing_costs_buy, rehab_cost_base, rehab_contingency, rehab_cost = (
        dollar_basis_and_rehab_cost_step(payload)
    )
    hml_amount, hml_points, monthly_hml_interest, total_hml_interest = hml_costs_step(payload, purchase_price, rehab_cost)
    monthly_taxes, monthly_insurance, monthly_operating, total_operating, total_holding_costs = (
        operating_and_holding_costs_step(payload, total_hml_interest)
    )
    agent_fees_percent, selling_closing_costs, selling_costs = selling_costs_step(payload, sale_price)

    down_payment_cash, cash_needed = total_cash_needed_step(
        payload, purchase_price, closing_costs_buy, hml_points, rehab_cost, total_operating, total_hml_interest,
    )
    total_cash_invested, total_cost_basis, gross_profit = cash_invested_and_cost_basis_step(
        purchase_price, rehab_cost, closing_costs_buy, total_holding_costs,
        selling_costs, hml_points, down_payment_cash, cash_needed.rehab_cash, sale_price,
    )
    capital_gains_tax, net_profit = net_profit_after_tax_step(payload, gross_profit)
    holding_years, roi, annualized_roi = roi_and_annualized_step(payload, net_profit, total_cash_invested)

    return FlipResultsWithIntermediates(
        purchase_price=purchase_price, sale_price=sale_price, closing_costs_buy=closing_costs_buy,
        rehab_cost_base=rehab_cost_base, rehab_contingency=rehab_contingency, rehab_cost=rehab_cost,
        hml_amount=hml_amount, hml_points=hml_points, monthly_hml_interest=monthly_hml_interest,
        total_hml_interest=total_hml_interest,
        monthly_taxes=monthly_taxes, monthly_insurance=monthly_insurance, monthly_operating=monthly_operating,
        total_operating=total_operating, total_holding_costs=total_holding_costs,
        agent_fees_percent=agent_fees_percent, selling_closing_costs=selling_closing_costs, selling_costs=selling_costs,
        down_payment_cash=down_payment_cash, rehab_cash=cash_needed.rehab_cash,
        total_cash_needed=cash_needed.without_buffer, total_cash_needed_with_buffer=cash_needed.with_buffer,
        rehab_float=cash_needed.rehab_float, buffered_closing=cash_needed.buffered_closing,
        buffered_operating=cash_needed.buffered_holding, buffered_interest=cash_needed.buffered_interest,
        total_cash_invested=total_cash_invested, total_cost_basis=total_cost_basis, gross_profit=gross_profit,
        capital_gains_tax=capital_gains_tax, net_profit=net_profit,
        holding_years=holding_years, roi=roi, annualized_roi=annualized_roi,
    )
