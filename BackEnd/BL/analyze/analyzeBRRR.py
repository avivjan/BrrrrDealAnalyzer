"""The BRRRR analysis -- the core of the product.

Two public entry points:

* `analyze_brrr` -- validate, then calculate. What `POST /analyze/brrr` calls.
* `calculate_brrr_results` -- the calculation itself, without validation. Also
  called by `BL.common.deal_response.create_deal_response` and by
  `BL.reports.reportBrrrPdf`.

`calculate_brrr_results` accepts either the Pydantic request model
(`analyzeBRRRReq`) or an ORM deal row -- everything downstream is duck-typed
attribute access, which is what lets `create_deal_response` pass a
`BrrrActiveDeal` straight in.

The calculation is broken into named steps under `brrrSteps/`, one file per
subject, mirroring the `breakdowns` dict's own metric groupings. Every step
function follows the same contract: it takes only the already-computed values
it needs, does its slice of `calc_*` calls *and* its slice of
`breakdown.add(...)` calls (so the self-documenting step registered next to a
value travels with the code that computes it), and returns only the new
value(s) later steps or the final response need.
"""

from ReqRes.common.analyze_inputs import analyzeBRRRReq
from ReqRes.common.analyze_results import analyzeBRRRRes
from BL.analyze.common.validation import validate_brrr_inputs
from BL.analyze.common.calc_breakdown import CalcBreakdown
from BL.analyze.brrrSteps.dollar_basis import dollar_basis_step
from BL.analyze.brrrSteps.hml_and_holding_costs import upfront_hml_and_holding_costs_step
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
    """Run every BRRRR calc step in order and assemble the response.

    Each step below is one self-contained piece of the calculation -- see the
    module docstring for the contract every step function follows. Reading
    top to bottom is reading the calculation itself; the metric keys threaded
    into `breakdown.add()` inside each step are what group these into the
    `breakdowns` dict the frontend/PDF render.
    """
    breakdown = CalcBreakdown()

    arv, purchase_price, rehab_cost = dollar_basis_step(payload)
    HML_interest_in_cash, HML_points_in_cash, holding_cost_until_refi = upfront_hml_and_holding_costs_step(
        payload, purchase_price, rehab_cost
    )
    operating_expenses = operating_expenses_step(payload, breakdown)
    closing_costs_buy, closing_cost_refi, ltv, refi_points_in_cash, cash_reserve_in_cash = refi_terms_step(payload, arv)

    cash_out_from_deal, cash_out_routi, loan_amount, hml_payoff, down_payment_cash = cash_out_at_refi_step(
        payload, breakdown, arv, ltv, purchase_price, rehab_cost, closing_costs_buy,
        HML_points_in_cash, HML_interest_in_cash, closing_cost_refi, refi_points_in_cash,
        cash_reserve_in_cash, holding_cost_until_refi,
    )
    mortgage_payment = mortgage_payment_step(payload, breakdown, arv, ltv, loan_amount)
    cash_flow = cash_flow_step(payload, breakdown, operating_expenses, mortgage_payment)
    dscr = dscr_step(payload, breakdown, mortgage_payment)
    cash_on_cash = cash_on_cash_step(breakdown, cash_out_from_deal, cash_flow)
    equity, net_profit = equity_and_net_profit_step(payload, breakdown, arv, ltv, cash_reserve_in_cash, cash_out_from_deal)
    roi = roi_step(breakdown, cash_out_from_deal, cash_flow, net_profit)
    total_cash_needed_without_buffer, total_cash_needed_with_buffer = total_cash_needed_step(
        payload, breakdown, purchase_price, down_payment_cash, closing_costs_buy,
        HML_points_in_cash, rehab_cost, HML_interest_in_cash, holding_cost_until_refi, hml_payoff,
    )

    return analyzeBRRRRes(
        cash_flow=cash_flow, dscr=dscr, cash_out=cash_out_from_deal, cash_out_routi=cash_out_routi, cash_on_cash=cash_on_cash,
        roi=roi, equity=equity, net_profit=net_profit,
        total_cash_needed_for_deal=total_cash_needed_without_buffer,
        total_cash_needed_for_deal_with_buffer=total_cash_needed_with_buffer,
        messages=None,
        breakdowns=breakdown.to_dict(),
    )
