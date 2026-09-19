"""BRRRR step: the lender-draw spread ("stolen money") and the rehab the investor funds in cash."""


def rehab_draw_step(rehab_cost, construction_budget):
    # Positive: the lender's draws exceed the spend and the excess is cash pulled out before
    # the refi. Negative: the investor injects that much beyond the budget.
    stolen_money = construction_budget - rehab_cost
    # The signed rehab term of the cash invested: what the budget does not cover
    # (negative when draws return cash). A 0 budget is the legacy cash-rehab case.
    rehab_cash = rehab_cost - construction_budget
    return stolen_money, rehab_cash
