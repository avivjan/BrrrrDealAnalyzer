"""The BRRRR/Flip orchestrators: run every calc helper and assemble the
self-documenting `breakdowns` alongside the headline metrics.

Both accept either the matching Pydantic request model (`analyzeBRRRReq` /
`analyzeFlipReq`) or an ORM deal row -- everything here is duck-typed attribute
access, which is what lets `BL.common.deal_response.create_deal_response` /
`create_bought_deal_response` pass a `BrrrActiveDeal`/`FlipActiveDeal` straight
in.
"""

from decimal import Decimal

from ReqRes.common.analyze_results import analyzeBRRRRes, analyzeFlipRes
from BL.common.calc_breakdown import CalcBreakdown, fmt_money, fmt_pct, fmt_num
from BL.common.deal_math import (
    thousands_to_dollars,
    get_HML_amount,
    calc_montly_operating_expenses,
    calcDSCR,
    calc_cash_out_from_deal,
    calc_cash_out_routi,
    calc_mortgage_payment,
    calc_cash_on_cash,
    calc_roi,
    calc_holding_costs,
    calc_HML_interest_in_cash,
    get_total_cash_needed_for_deal,
)


def calculate_brrr_results(payload) -> analyzeBRRRRes:
    # Self-documenting calculation: each intermediate variable below registers
    # its own CalcStep next to the line that produces it. Math is unchanged.
    breakdown = CalcBreakdown()

    arv = thousands_to_dollars(payload.arv_in_thousands)
    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost_base = thousands_to_dollars(payload.rehab_cost_in_thousands)
    contingency = rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0"))
    rehab_cost = rehab_cost_base + contingency

    HML_interest_in_cash = calc_HML_interest_in_cash(purchase_price, payload.down_payment, rehab_cost, payload.days_until_refi, payload.HML_interest_rate, payload.use_HM_for_rehab)
    HML_points_in_cash = payload.HML_points/Decimal("100.0") * get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    holding_cost_until_refi = calc_holding_costs(payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, payload.days_until_refi)

    operating_expenses = calc_montly_operating_expenses(payload)
    breakdown.add(
        "cash_flow",
        "Monthly Operating Expenses",
        operating_expenses,
        f"Rent ({fmt_money(payload.rent)}) × (Vacancy {fmt_pct(payload.vacancy_percent)} + Mgmt {fmt_pct(payload.property_managment_fee_precentages_from_rent)} + Maint {fmt_pct(payload.maintenance_percent)} + CapEx {fmt_pct(payload.capex_percent_of_rent)}) + Taxes ({fmt_money(payload.annual_property_taxes)})/12 + Insurance ({fmt_money(payload.annual_insurance)})/12 + HOA ({fmt_money(payload.montly_hoa)}) = {fmt_money(operating_expenses)}",
    )
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)
    closing_cost_refi = thousands_to_dollars(payload.closing_cost_refi_in_thousands)
    ltv = payload.ltv_as_precent/Decimal("100")
    refi_points_in_cash = (payload.refi_points / Decimal("100")) * arv * ltv
    cash_reserve_in_cash = thousands_to_dollars(payload.cash_reserve_in_thousands)

    cash_out_from_deal = calc_cash_out_from_deal(arv, ltv, payload.down_payment, purchase_price, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, closing_cost_refi, refi_points_in_cash, payload.use_HM_for_rehab, holding_cost_until_refi, cash_reserve_in_cash)
    # Decompose the helper's inputs only for the formula narrative (no math change).
    _brrr_loan_amount = arv * ltv
    breakdown.add(
        ["cash_out", "equity"],
        "Refi Loan Amount",
        _brrr_loan_amount,
        f"ARV ({fmt_money(arv)}) × LTV {fmt_pct(payload.ltv_as_precent)} = {fmt_money(_brrr_loan_amount)}",
    )
    _brrr_hml_payoff = get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    breakdown.add(
        "cash_out",
        "HML Payoff at Refi",
        _brrr_hml_payoff,
        (f"Purchase Loan + Rehab ({fmt_money(_brrr_hml_payoff)}) — full HM stack carried into refi"
         if payload.use_HM_for_rehab
         else f"Purchase Loan only = (1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(purchase_price)}) = {fmt_money(_brrr_hml_payoff)}"),
    )
    _brrr_down_payment_cash = (payload.down_payment / Decimal("100")) * purchase_price
    _brrr_total_cash_invested = _brrr_down_payment_cash + closing_costs_buy + HML_points_in_cash + rehab_cost * (1 - int(payload.use_HM_for_rehab)) + HML_interest_in_cash + holding_cost_until_refi
    breakdown.add(
        "cash_out",
        "Total Cash Invested (pre-refi)",
        _brrr_total_cash_invested,
        f"Down Payment ({fmt_money(_brrr_down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(HML_points_in_cash)}) + Rehab Out-of-Pocket ({fmt_money(rehab_cost * (1 - int(payload.use_HM_for_rehab)))}) + HML Interest ({fmt_money(HML_interest_in_cash)}) + Holding ({fmt_money(holding_cost_until_refi)}) = {fmt_money(_brrr_total_cash_invested)}",
    )
    breakdown.add(
        ["net_profit", "roi", "cash_on_cash", "cash_out"],
        "Cash Out from Deal",
        cash_out_from_deal,
        f"Refi Loan ({fmt_money(_brrr_loan_amount)}) − HML Payoff ({fmt_money(_brrr_hml_payoff)}) − Refi Closing ({fmt_money(closing_cost_refi)}) − Refi Points ({fmt_money(refi_points_in_cash)}) − Cash Reserve ({fmt_money(cash_reserve_in_cash)}) − Total Cash Invested ({fmt_money(_brrr_total_cash_invested)}) = {fmt_money(cash_out_from_deal)}",
    )
    cash_out_routi = calc_cash_out_routi(arv, ltv, payload.down_payment, purchase_price, rehab_cost, closing_cost_refi, refi_points_in_cash, payload.use_HM_for_rehab, cash_reserve_in_cash)
    mortgage_payment = calc_mortgage_payment(arv, ltv, payload.interest_rate, payload.loan_term_years)
    breakdown.add(
        ["cash_flow", "dscr"],
        "Monthly Mortgage Payment",
        mortgage_payment,
        f"Amortize Loan ({fmt_money(_brrr_loan_amount)} = ARV {fmt_money(arv)} × LTV {fmt_pct(payload.ltv_as_precent)}) at {fmt_pct(payload.interest_rate)}/yr over {payload.loan_term_years} years = {fmt_money(mortgage_payment)}",
    )

    net_operating_income = payload.rent - operating_expenses
    breakdown.add(
        "cash_flow",
        "Net Operating Income (NOI)",
        net_operating_income,
        f"Rent ({fmt_money(payload.rent)}) − Operating Expenses ({fmt_money(operating_expenses)}) = {fmt_money(net_operating_income)}",
    )
    cash_flow = net_operating_income - mortgage_payment
    breakdown.add(
        ["cash_flow", "roi", "cash_on_cash"],
        "Monthly Cash Flow",
        cash_flow,
        f"NOI ({fmt_money(net_operating_income)}) − Mortgage ({fmt_money(mortgage_payment)}) = {fmt_money(cash_flow)}",
    )
    dscr =  calcDSCR(payload.rent, payload.annual_property_taxes, payload.annual_insurance, payload.montly_hoa, mortgage_payment)
    # Decompose PITIA only for the formula narrative (matches calcDSCR internals).
    _brrr_pitia = mortgage_payment + payload.annual_property_taxes / Decimal("12.0") + payload.annual_insurance / Decimal("12.0") + payload.montly_hoa
    breakdown.add(
        "dscr",
        "DSCR",
        dscr,
        (f"Rent ({fmt_money(payload.rent)}) / PITIA ({fmt_money(_brrr_pitia)} = Mortgage + Taxes/12 + Ins/12 + HOA) = {fmt_num(dscr)}"
         if _brrr_pitia else "PITIA is 0 → DSCR undefined"),
    )
    cash_on_cash = calc_cash_on_cash(cash_out_from_deal, cash_flow)
    if cash_out_from_deal >= 0:
        _brrr_coc_formula = f"Cash Out ({fmt_money(cash_out_from_deal)}) ≥ 0 → no equity at risk (∞)"
    elif cash_flow <= 0:
        _brrr_coc_formula = f"Cash Flow ({fmt_money(cash_flow)}) ≤ 0 → CoC undefined (-∞)"
    else:
        _brrr_coc_formula = f"Annual Cash Flow ({fmt_money(cash_flow * 12)}) / |Cash Out| ({fmt_money(abs(cash_out_from_deal))}) × 100 = {fmt_pct(cash_on_cash)}"
    breakdown.add("cash_on_cash", "Cash on Cash", cash_on_cash, _brrr_coc_formula)
    # Cash reserve is treated as an immediate principal paydown on the DSCR
    # loan, so the post-refi loan balance is `arv*ltv - cash_reserve`. That
    # paydown converts cash_out into equity 1:1, leaving net_profit unchanged
    # (CoC and ROI still drop because more capital is tied up in the deal).
    equity = arv * (1 - ltv) + cash_reserve_in_cash
    breakdown.add(
        ["net_profit", "roi", "equity"],
        "Equity (post-refi)",
        equity,
        f"ARV ({fmt_money(arv)}) × (1 − LTV {fmt_pct(payload.ltv_as_precent)}) + Cash Reserve ({fmt_money(cash_reserve_in_cash)}) = {fmt_money(equity)}",
    )
    net_profit = equity + cash_out_from_deal
    breakdown.add(
        ["net_profit", "roi"],
        "Net Profit",
        net_profit,
        f"Equity ({fmt_money(equity)}) + Cash Out ({fmt_money(cash_out_from_deal)}) = {fmt_money(net_profit)}",
    )
    roi = calc_roi(cash_out_from_deal, cash_flow, net_profit)
    if cash_out_from_deal >= 0:
        _brrr_roi_formula = f"Cash Out ({fmt_money(cash_out_from_deal)}) ≥ 0 → no equity at risk (∞)"
    elif cash_flow <= 0:
        _brrr_roi_formula = f"Cash Flow ({fmt_money(cash_flow)}) ≤ 0 → ROI undefined (-∞)"
    else:
        _brrr_roi_formula = f"(Annual Cash Flow ({fmt_money(cash_flow * 12)}) + Net Profit ({fmt_money(net_profit)})) / |Cash Out| ({fmt_money(abs(cash_out_from_deal))}) × 100 = {fmt_pct(roi)}"
    breakdown.add("roi", "ROI", roi, _brrr_roi_formula)
    total_cash_needed_without_buffer, total_cash_needed_with_buffer = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, holding_cost_until_refi, closing_costs_buy, HML_points_in_cash, rehab_cost, HML_interest_in_cash, payload.use_HM_for_rehab)
    # Surface the same components the helper sums internally so the user can
    # follow each dollar that goes into the unbuffered total.
    _brrr_rehab_cash_needed = rehab_cost * (1 - int(payload.use_HM_for_rehab))
    breakdown.add(
        ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"],
        "Down Payment (cash)",
        _brrr_down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(purchase_price)}) = {fmt_money(_brrr_down_payment_cash)}",
    )
    breakdown.add(
        ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"],
        "Closing Costs (Buy)",
        closing_costs_buy,
        f"{fmt_money(closing_costs_buy)}",
    )
    breakdown.add(
        ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"],
        "HML Points (cash)",
        HML_points_in_cash,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(_brrr_hml_payoff)}) = {fmt_money(HML_points_in_cash)}",
    )
    breakdown.add(
        ["total_cash_needed_for_deal", "total_cash_needed_for_deal_with_buffer"],
        "Rehab Cash (out-of-pocket)",
        _brrr_rehab_cash_needed,
        (f"Rehab ({fmt_money(rehab_cost)}) is financed via HM → no out-of-pocket = {fmt_money(_brrr_rehab_cash_needed)}"
         if payload.use_HM_for_rehab
         else f"Rehab ({fmt_money(rehab_cost)}) paid in cash = {fmt_money(_brrr_rehab_cash_needed)}"),
    )
    breakdown.add(
        "total_cash_needed_for_deal",
        "HML Interest (cash, until refi)",
        HML_interest_in_cash,
        f"{fmt_money(HML_interest_in_cash)} accrued over {payload.days_until_refi} days at {fmt_pct(payload.HML_interest_rate)}/yr ÷ 360 per diem",
    )
    breakdown.add(
        "total_cash_needed_for_deal",
        "Holding Costs (until refi)",
        holding_cost_until_refi,
        f"Taxes + Insurance + HOA accrued over {payload.days_until_refi} days = {fmt_money(holding_cost_until_refi)}",
    )
    breakdown.add(
        "total_cash_needed_for_deal",
        "Total Cash Needed",
        total_cash_needed_without_buffer,
        f"Down Payment ({fmt_money(_brrr_down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(HML_points_in_cash)}) + Rehab Cash ({fmt_money(_brrr_rehab_cash_needed)}) + HML Interest ({fmt_money(HML_interest_in_cash)}) + Holding ({fmt_money(holding_cost_until_refi)}) = {fmt_money(total_cash_needed_without_buffer)}",
    )
    # Buffered version applies the same multipliers the helper uses internally
    # (closing × 1.1, holding × 1.5, HML interest × 1.5, rehab × 1.5).
    _brrr_buffered_closing = closing_costs_buy * Decimal("1.1")
    _brrr_buffered_holding = holding_cost_until_refi * Decimal("1.5")
    _brrr_buffered_interest = HML_interest_in_cash * Decimal("1.5")
    breakdown.add(
        "total_cash_needed_for_deal_with_buffer",
        "Closing × 1.1 buffer",
        _brrr_buffered_closing,
        f"Closing ({fmt_money(closing_costs_buy)}) × 1.1 = {fmt_money(_brrr_buffered_closing)}",
    )
    breakdown.add(
        "total_cash_needed_for_deal_with_buffer",
        "HML Interest × 1.5 buffer",
        _brrr_buffered_interest,
        f"HML Interest ({fmt_money(HML_interest_in_cash)}) × 1.5 = {fmt_money(_brrr_buffered_interest)}",
    )
    breakdown.add(
        "total_cash_needed_for_deal_with_buffer",
        "Holding × 1.5 buffer",
        _brrr_buffered_holding,
        f"Holding ({fmt_money(holding_cost_until_refi)}) × 1.5 = {fmt_money(_brrr_buffered_holding)}",
    )
    breakdown.add(
        "total_cash_needed_for_deal_with_buffer",
        "Total Cash Needed (Buffered)",
        total_cash_needed_with_buffer,
        f"Down Payment ({fmt_money(_brrr_down_payment_cash)}) + Closing×1.1 ({fmt_money(_brrr_buffered_closing)}) + HML Points ({fmt_money(HML_points_in_cash)}) + Rehab Cash ({fmt_money(_brrr_rehab_cash_needed)}) + HML Interest×1.5 ({fmt_money(_brrr_buffered_interest)}) + Holding×1.5 ({fmt_money(_brrr_buffered_holding)}) = {fmt_money(total_cash_needed_with_buffer)}",
    )

    return analyzeBRRRRes(
        cash_flow=cash_flow, dscr=dscr, cash_out=cash_out_from_deal, cash_out_routi=cash_out_routi, cash_on_cash=cash_on_cash,
        roi=roi, equity=equity, net_profit=net_profit,
        total_cash_needed_for_deal=total_cash_needed_without_buffer,
        total_cash_needed_for_deal_with_buffer=total_cash_needed_with_buffer,
        messages=None,
        breakdowns=breakdown.to_dict(),
    )


def calculate_flip_results(payload) -> analyzeFlipRes:
    # Self-documenting calculation: each intermediate variable below registers
    # its own CalcStep next to the line that produces it. Math is unchanged.
    breakdown = CalcBreakdown()

    purchase_price = thousands_to_dollars(payload.purchase_price_in_thousands)
    rehab_cost_base = thousands_to_dollars(payload.rehab_cost_in_thousands)
    contingency = rehab_cost_base * (payload.rehab_contingency_percent / Decimal("100.0"))
    rehab_cost = rehab_cost_base + contingency
    breakdown.add(
        "net_profit",
        "Rehab Cost (with contingency)",
        rehab_cost,
        f"Base ({fmt_money(rehab_cost_base)}) + Contingency {fmt_pct(payload.rehab_contingency_percent)} ({fmt_money(contingency)}) = {fmt_money(rehab_cost)}",
    )
    sale_price = thousands_to_dollars(payload.sale_price_in_thousands)
    closing_costs_buy = thousands_to_dollars(payload.closing_costs_buy_in_thousands)

    hml_amount = get_HML_amount(purchase_price, payload.down_payment, rehab_cost, payload.use_HM_for_rehab)
    breakdown.add(
        "total_hml_interest",
        "HML Amount",
        hml_amount,
        (f"Purchase Loan + Rehab ({fmt_money(hml_amount)}) — full HM stack"
         if payload.use_HM_for_rehab
         else f"Purchase Loan only = (1 − Down Payment {fmt_pct(payload.down_payment)}) × Purchase ({fmt_money(purchase_price)}) = {fmt_money(hml_amount)}"),
    )
    hml_points_cash = (payload.HML_points / Decimal("100.0")) * hml_amount
    breakdown.add(
        "net_profit",
        "HML Points (cash)",
        hml_points_cash,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(hml_amount)}) = {fmt_money(hml_points_cash)}",
    )

    monthly_interest = (payload.HML_interest_rate / Decimal("100.0") / Decimal("12.0")) * hml_amount
    breakdown.add(
        "total_hml_interest",
        "Monthly HML Interest",
        monthly_interest,
        f"HML Amount ({fmt_money(hml_amount)}) × {fmt_pct(payload.HML_interest_rate)}/yr ÷ 12 = {fmt_money(monthly_interest)}",
    )
    total_hml_interest = monthly_interest * payload.holding_time_months
    breakdown.add(
        ["net_profit", "total_hml_interest", "total_holding_costs"],
        "Total HML Interest (over holding period)",
        total_hml_interest,
        f"Monthly Interest ({fmt_money(monthly_interest)}) × {payload.holding_time_months} mos = {fmt_money(total_hml_interest)}",
    )

    monthly_taxes = payload.annual_property_taxes / Decimal("12.0")
    monthly_insurance = payload.annual_insurance / Decimal("12.0")
    monthly_operating = monthly_taxes + monthly_insurance + payload.montly_hoa + payload.monthly_utilities
    total_operating = monthly_operating * payload.holding_time_months
    breakdown.add(
        ["net_profit", "total_holding_costs"],
        "Total Operating Costs (during holding)",
        total_operating,
        f"(Taxes/12 ({fmt_money(monthly_taxes)}) + Insurance/12 ({fmt_money(monthly_insurance)}) + HOA ({fmt_money(payload.montly_hoa)}) + Utilities ({fmt_money(payload.monthly_utilities)})) × {payload.holding_time_months} mos = {fmt_money(total_operating)}",
    )

    total_holding_costs = total_hml_interest + total_operating
    breakdown.add(
        ["net_profit", "total_holding_costs"],
        "Total Holding Costs",
        total_holding_costs,
        f"HML Interest ({fmt_money(total_hml_interest)}) + Operating ({fmt_money(total_operating)}) = {fmt_money(total_holding_costs)}",
    )

    agent_fees_percent = payload.buyer_agent_selling_fee + payload.seller_agent_selling_fee
    selling_costs = sale_price * (agent_fees_percent / Decimal("100.0")) + thousands_to_dollars(payload.selling_closing_costs_in_thousands)
    breakdown.add(
        "net_profit",
        "Selling Costs",
        selling_costs,
        f"Sale Price ({fmt_money(sale_price)}) × Agent Fees {fmt_pct(agent_fees_percent)} + Closing ({fmt_money(thousands_to_dollars(payload.selling_closing_costs_in_thousands))}) = {fmt_money(selling_costs)}",
    )

    down_payment_cash = (payload.down_payment / Decimal("100.0")) * purchase_price
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Down Payment (cash)",
        down_payment_cash,
        f"{fmt_pct(payload.down_payment)} × Purchase ({fmt_money(purchase_price)}) = {fmt_money(down_payment_cash)}",
    )
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Closing Costs (Buy)",
        closing_costs_buy,
        f"{fmt_money(closing_costs_buy)}",
    )
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "HML Points (cash)",
        hml_points_cash,
        f"{fmt_pct(payload.HML_points)} × HML Amount ({fmt_money(hml_amount)}) = {fmt_money(hml_points_cash)}",
    )

    total_cash_needed_without_buffer, total_cash_needed_with_buffer = get_total_cash_needed_for_deal(payload.down_payment, purchase_price, total_operating, closing_costs_buy, hml_points_cash, rehab_cost, total_hml_interest, payload.use_HM_for_rehab)
    rehab_cash = rehab_cost if not payload.use_HM_for_rehab else Decimal("0")
    breakdown.add(
        ["total_cash_needed", "total_cash_needed_with_buffer"],
        "Rehab Cash (out-of-pocket)",
        rehab_cash,
        (f"Rehab ({fmt_money(rehab_cost)}) is financed via HM → no out-of-pocket = {fmt_money(rehab_cash)}"
         if payload.use_HM_for_rehab
         else f"Rehab ({fmt_money(rehab_cost)}) paid in cash = {fmt_money(rehab_cash)}"),
    )
    breakdown.add(
        "total_cash_needed",
        "HML Interest (cash, during holding)",
        total_hml_interest,
        f"Monthly Interest × {payload.holding_time_months} mos = {fmt_money(total_hml_interest)}",
    )
    breakdown.add(
        "total_cash_needed",
        "Operating Costs (during holding)",
        total_operating,
        f"Monthly Operating × {payload.holding_time_months} mos = {fmt_money(total_operating)}",
    )
    breakdown.add(
        "total_cash_needed",
        "Total Cash Needed",
        total_cash_needed_without_buffer,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(hml_points_cash)}) + Rehab Cash ({fmt_money(rehab_cash)}) + HML Interest ({fmt_money(total_hml_interest)}) + Operating ({fmt_money(total_operating)}) = {fmt_money(total_cash_needed_without_buffer)}",
    )
    # Buffered version mirrors `get_total_cash_needed_for_deal` internals:
    # operating × 1.5, interest × 1.5, closing × 1.1.
    _flip_buffered_closing = closing_costs_buy * Decimal("1.1")
    _flip_buffered_interest = total_hml_interest * Decimal("1.5")
    _flip_buffered_operating = total_operating * Decimal("1.5")
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Closing × 1.1 buffer",
        _flip_buffered_closing,
        f"Closing ({fmt_money(closing_costs_buy)}) × 1.1 = {fmt_money(_flip_buffered_closing)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "HML Interest × 1.5 buffer",
        _flip_buffered_interest,
        f"HML Interest ({fmt_money(total_hml_interest)}) × 1.5 = {fmt_money(_flip_buffered_interest)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Operating × 1.5 buffer",
        _flip_buffered_operating,
        f"Operating ({fmt_money(total_operating)}) × 1.5 = {fmt_money(_flip_buffered_operating)}",
    )
    breakdown.add(
        "total_cash_needed_with_buffer",
        "Total Cash Needed (Buffered)",
        total_cash_needed_with_buffer,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing×1.1 ({fmt_money(_flip_buffered_closing)}) + HML Points ({fmt_money(hml_points_cash)}) + Rehab Cash ({fmt_money(rehab_cash)}) + HML Interest×1.5 ({fmt_money(_flip_buffered_interest)}) + Operating×1.5 ({fmt_money(_flip_buffered_operating)}) = {fmt_money(total_cash_needed_with_buffer)}",
    )

    total_cash_invested = down_payment_cash + closing_costs_buy + hml_points_cash + total_holding_costs + rehab_cash
    breakdown.add(
        "roi",
        "Total Cash Invested",
        total_cash_invested,
        f"Down Payment ({fmt_money(down_payment_cash)}) + Closing ({fmt_money(closing_costs_buy)}) + HML Points ({fmt_money(hml_points_cash)}) + Holding ({fmt_money(total_holding_costs)}) + Rehab Out-of-Pocket ({fmt_money(rehab_cash)}) = {fmt_money(total_cash_invested)}",
    )

    # Cost basis for profit calc
    total_cost_basis = purchase_price + rehab_cost + closing_costs_buy + total_holding_costs + selling_costs + hml_points_cash
    breakdown.add(
        "net_profit",
        "Total Cost Basis",
        total_cost_basis,
        f"Purchase ({fmt_money(purchase_price)}) + Rehab ({fmt_money(rehab_cost)}) + Closing ({fmt_money(closing_costs_buy)}) + Holding ({fmt_money(total_holding_costs)}) + Selling ({fmt_money(selling_costs)}) + HML Points ({fmt_money(hml_points_cash)}) = {fmt_money(total_cost_basis)}",
    )

    gross_profit = sale_price - total_cost_basis
    breakdown.add(
        "net_profit",
        "Gross Profit",
        gross_profit,
        f"Sale Price ({fmt_money(sale_price)}) − Total Cost Basis ({fmt_money(total_cost_basis)}) = {fmt_money(gross_profit)}",
    )

    cap_gains = Decimal("0")
    if gross_profit > 0:
        cap_gains = gross_profit * (payload.capital_gains_tax_rate / Decimal("100.0"))
    breakdown.add(
        "net_profit",
        "Capital Gains Tax",
        cap_gains,
        (f"Gross Profit ({fmt_money(gross_profit)}) × {fmt_pct(payload.capital_gains_tax_rate)} = {fmt_money(cap_gains)}"
         if gross_profit > 0 else f"Gross Profit ≤ 0 → no tax owed = {fmt_money(cap_gains)}"),
    )

    net_profit = gross_profit - cap_gains
    breakdown.add(
        ["net_profit", "roi"],
        "Net Profit (after tax)",
        net_profit,
        f"Gross Profit ({fmt_money(gross_profit)}) − Capital Gains Tax ({fmt_money(cap_gains)}) = {fmt_money(net_profit)}",
    )

    roi = (net_profit / total_cash_invested) * Decimal("100.0") if total_cash_invested > 0 else Decimal("0")
    breakdown.add(
        ["roi", "annualized_roi"],
        "ROI",
        roi,
        (f"Net Profit ({fmt_money(net_profit)}) / Total Cash Invested ({fmt_money(total_cash_invested)}) × 100 = {fmt_pct(roi)}"
         if total_cash_invested > 0 else "Total Cash Invested is 0 → ROI = 0%"),
    )
    years = payload.holding_time_months / Decimal("12.0")
    annualized_roi = (roi / years) if years > 0 else Decimal("0")
    breakdown.add(
        "annualized_roi",
        "Annualized ROI",
        annualized_roi,
        (f"ROI ({fmt_pct(roi)}) / Holding Years ({fmt_num(years)}) = {fmt_pct(annualized_roi)}"
         if years > 0 else "Holding time is 0 → Annualized ROI = 0%"),
    )

    return analyzeFlipRes(
        net_profit=net_profit, roi=roi, annualized_roi=annualized_roi,
        total_cash_needed=total_cash_needed_without_buffer,
        total_cash_needed_with_buffer=total_cash_needed_with_buffer,
        total_holding_costs=total_holding_costs,
        total_hml_interest=total_hml_interest, messages=[],
        breakdowns=breakdown.to_dict(),
    )
