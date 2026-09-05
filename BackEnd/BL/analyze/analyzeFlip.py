"""The Flip analysis -- the core of the product.

Two public entry points:

* `analyze_flip` -- validate, then calculate. What `POST /analyze/flip` calls.
* `calculate_flip_results` -- the calculation itself, without validation. Also
  called by `BL.common.deal_response.create_deal_response` and by
  `BL.reports.reportFlipPdf`.

`calculate_flip_results` accepts either the Pydantic request model
(`analyzeFlipReq`) or an ORM deal row -- everything downstream is duck-typed
attribute access, which is what lets `create_deal_response` pass a
`FlipActiveDeal` straight in.

The calculation is broken into named steps under `flipSteps/`, one file per
subject, mirroring the `breakdowns` dict's own metric groupings. Every step
function follows the same contract: it takes only the already-computed values
it needs, does its slice of `calc_*` calls *and* its slice of
`breakdown.add(...)` calls, and returns only the new value(s) later steps or
the final response need.
"""

from ReqRes.common.analyze_inputs import analyzeFlipReq
from ReqRes.common.analyze_results import analyzeFlipRes
from BL.analyze.common.validation import validate_flip_inputs
from BL.analyze.common.calc_breakdown import CalcBreakdown
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
    """Run every Flip calc step in order and assemble the response.

    Each step below is one self-contained piece of the calculation -- see the
    module docstring for the contract every step function follows. Reading
    top to bottom is reading the calculation itself; the metric keys threaded
    into `breakdown.add()` inside each step are what group these into the
    `breakdowns` dict the frontend/PDF render.
    """
    breakdown = CalcBreakdown()

    purchase_price, sale_price, closing_costs_buy, rehab_cost = dollar_basis_and_rehab_cost_step(payload, breakdown)
    hml_amount, hml_points_cash, total_hml_interest = hml_costs_step(payload, breakdown, purchase_price, rehab_cost)
    total_operating, total_holding_costs = operating_and_holding_costs_step(payload, breakdown, total_hml_interest)
    selling_costs = selling_costs_step(payload, breakdown, sale_price)

    total_cash_needed_without_buffer, total_cash_needed_with_buffer, down_payment_cash, rehab_cash = total_cash_needed_step(
        payload, breakdown, purchase_price, closing_costs_buy, hml_amount, hml_points_cash, rehab_cost,
        total_operating, total_hml_interest,
    )
    total_cash_invested, gross_profit = cash_invested_and_cost_basis_step(
        payload, breakdown, purchase_price, rehab_cost, closing_costs_buy, total_holding_costs,
        selling_costs, hml_points_cash, down_payment_cash, rehab_cash, sale_price,
    )
    net_profit = net_profit_after_tax_step(payload, breakdown, gross_profit)
    roi, annualized_roi = roi_and_annualized_step(payload, breakdown, net_profit, total_cash_invested)

    return analyzeFlipRes(
        net_profit=net_profit, roi=roi, annualized_roi=annualized_roi,
        total_cash_needed=total_cash_needed_without_buffer,
        total_cash_needed_with_buffer=total_cash_needed_with_buffer,
        total_holding_costs=total_holding_costs,
        total_hml_interest=total_hml_interest, messages=[],
        breakdowns=breakdown.to_dict(),
    )
