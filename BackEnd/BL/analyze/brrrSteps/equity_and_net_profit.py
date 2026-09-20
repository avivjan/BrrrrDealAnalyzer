"""BRRRR step: post-refi equity and net profit."""


def equity_and_net_profit_step(arv, ltv, reserves_total, cash_out):
    # The reserves are escrowed at refi and returned at exit/sale. They are NOT a principal
    # paydown: the DSCR loan (and its payment/DSCR) stays on the full `arv*ltv`. Because they
    # are recoverable they count as equity, converting cash_out into equity 1:1 and leaving
    # net_profit unchanged (CoC and ROI still drop because more capital is tied up).
    equity = arv * (1 - ltv) + reserves_total
    net_profit = equity + cash_out
    return equity, net_profit
