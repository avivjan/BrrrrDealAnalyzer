"""The BRRRR analysis -- the core of the product.

Three public entry points:

* `analyze_brrr` -- validate, then calculate. What `POST /analyze/brrr` calls.
* `calculate_brrr_results` -- the calculation plus its explanation, without
  validation. Also called by `BL.common.deal_response.create_deal_response`
  and by `BL.reports.reportBrrrPdf`.
* `compute_brrr` -- the numbers only, as a `BrrrCalc` record. No strings, no
  formatting; the thing to call for batch or high-frequency use.

`compute_brrr` accepts either the Pydantic request model (`analyzeBRRRReq`)
or an ORM deal row -- everything downstream is duck-typed attribute access,
which is what lets `create_deal_response` pass a `BrrrActiveDeal` straight in.

The calculation is broken into named steps under `brrrSteps/`, one file per
subject. Every step is pure: it takes the already-computed values it needs
and returns only the new ones. The narrative behind each number lives in the
companion module `BL/analyze/explain/brrr.py`, which reads the finished
`BrrrCalc` and never recomputes anything.
"""

from ReqRes.common.analyze_inputs import analyzeBRRRReq
from ReqRes.common.analyze_results import analyzeBRRRRes
from BL.analyze.common.validation import validate_brrr_inputs
from BL.analyze.brrr_calc import BrrrCalc
from BL.analyze.explain.brrr import explain_brrr
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
    """Numbers plus their explanation, as the API response model."""
    calc = compute_brrr(payload)
    return analyzeBRRRRes(
        cash_flow=calc.cash_flow, dscr=calc.dscr, cash_out=calc.cash_out,
        cash_out_routi=calc.cash_out_routi, cash_on_cash=calc.cash_on_cash,
        roi=calc.roi, equity=calc.equity, net_profit=calc.net_profit,
        total_cash_needed_for_deal=calc.total_cash_needed,
        total_cash_needed_for_deal_with_buffer=calc.total_cash_needed_with_buffer,
        messages=None,
        breakdowns=explain_brrr(payload, calc),
    )


def compute_brrr(payload) -> BrrrCalc:
    """Run every BRRRR calc step in order. Reading top to bottom is reading the calculation."""
    arv, purchase_price, rehab_cost_base, rehab_contingency, rehab_cost = dollar_basis_step(payload)
    hml_amount, hml_interest, hml_points, holding_costs = upfront_hml_and_holding_costs_step(
        payload, purchase_price, rehab_cost
    )
    operating_expenses = operating_expenses_step(payload)
    closing_costs_buy, closing_costs_refi, ltv, refi_points, cash_reserve = refi_terms_step(payload, arv)

    loan_amount, down_payment_cash, total_cash_invested, cash_out_routi, cash_out = cash_out_at_refi_step(
        payload, arv, ltv, purchase_price, rehab_cost, closing_costs_buy,
        hml_points, hml_interest, closing_costs_refi, refi_points, cash_reserve, holding_costs,
    )
    mortgage_payment = mortgage_payment_step(payload, arv, ltv)
    net_operating_income, cash_flow = cash_flow_step(payload, operating_expenses, mortgage_payment)
    pitia, dscr = dscr_step(payload, mortgage_payment)
    cash_on_cash = cash_on_cash_step(cash_out, cash_flow)
    equity, net_profit = equity_and_net_profit_step(arv, ltv, cash_reserve, cash_out)
    roi = roi_step(cash_out, cash_flow, net_profit)
    refi_shortfall, cash_needed = total_cash_needed_step(
        payload, purchase_price, closing_costs_buy, hml_points, rehab_cost, hml_interest,
        holding_costs, cash_out_routi,
    )

    return BrrrCalc(
        arv=arv, purchase_price=purchase_price, rehab_cost_base=rehab_cost_base,
        rehab_contingency=rehab_contingency, rehab_cost=rehab_cost,
        hml_amount=hml_amount, hml_points=hml_points, hml_interest=hml_interest, holding_costs=holding_costs,
        closing_costs_buy=closing_costs_buy, closing_costs_refi=closing_costs_refi, ltv=ltv,
        refi_points=refi_points, cash_reserve=cash_reserve,
        loan_amount=loan_amount, down_payment_cash=down_payment_cash, rehab_cash=cash_needed.rehab_cash,
        total_cash_invested=total_cash_invested, cash_out_routi=cash_out_routi, cash_out=cash_out,
        operating_expenses=operating_expenses, mortgage_payment=mortgage_payment,
        net_operating_income=net_operating_income, cash_flow=cash_flow, pitia=pitia, dscr=dscr,
        cash_on_cash=cash_on_cash, equity=equity, net_profit=net_profit, roi=roi,
        refi_shortfall=refi_shortfall,
        total_cash_needed=cash_needed.without_buffer,
        total_cash_needed_with_buffer=cash_needed.with_buffer,
        rehab_float=cash_needed.rehab_float, buffered_closing=cash_needed.buffered_closing,
        buffered_holding=cash_needed.buffered_holding, buffered_interest=cash_needed.buffered_interest,
    )
