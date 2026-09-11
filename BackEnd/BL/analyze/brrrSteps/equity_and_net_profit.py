"""BRRRR step: post-refi equity and net profit."""


def equity_and_net_profit_step(arv, ltv, cash_reserve, cash_out):
    # Cash reserve is cash escrowed at refi and returned at exit/sale. It is
    # NOT a principal paydown: the DSCR loan (and its payment/DSCR) stays on the
    # full `arv*ltv`. Because the reserve is recoverable it is counted as
    # equity, converting cash_out into equity 1:1 and leaving net_profit
    # unchanged (CoC and ROI still drop because more capital is tied up).
    equity = arv * (1 - ltv) + cash_reserve
    net_profit = equity + cash_out
    return equity, net_profit
