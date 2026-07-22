"""Waterfall Priority Engine.

When a rent payment lands, the liquid cash it brings must be allocated in a
strict priority order so the mortgage is never at risk, historical reserve
debt is repaid before new savings accrue, and every physical Checking ->
Savings movement is queued for the 11th settlement sweep rather than moved
ad-hoc.

The engine is a **pure function**: it takes an immutable snapshot of the
inputs and returns a fully-described plan (`WaterfallResult`) without
touching the database. A separate thin `apply_waterfall_to_property` adapter
persists that plan. Keeping the math pure makes every rule in the 5-step
sequence exhaustively unit-testable in isolation.

The 5-step sequence (Steps 0 through 4):

  STEP 0  Imminent P&I Provisioning
          Retain, out of the incoming cash, whatever is still needed on top
          of the current Checking balance to cover the upcoming 10th P&I
          mortgage draft. Only the remainder flows down the waterfall.

  STEP 1  Clear Historical Reserve Debt (`reserve_debt`)
          Repay `reserve_debt` back toward $0, restoring
          `reserve_bucket_balance` and queueing a physical transfer
          (`reserve_to_settle += cleared`) for the 11th sweep.

  STEP 2  Current Month Tax Allocation (`target_tax_allocation`)
          Virtually accrue tax into `tax_bucket_balance`, queueing a
          physical transfer (`tax_to_settle += tax`) for the 11th sweep.

  STEP 3  Current Month Reserve Allocation & Cap Fill
          Fund the reserve target (`base_rent_target * pct / 100`), filling
          up to the exact `reserve_bucket_cap`. Any portion that would breach
          the cap is frozen as 'Pending User Overflow Decision' (UI options
          A/B/C). When `chase_reserves` is True, also chase past uncollected
          reserve targets.

  STEP 4  Clean Cash Flow
          Whatever unencumbered cash remains is net operating cash flow that
          stays in Checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List

_CENTS = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(_CENTS)


@dataclass(frozen=True)
class WaterfallInput:
    """Immutable snapshot fed into the engine.

    `rent_received` is the incoming liquid cash to allocate.
    `checking_balance` is the Checking balance BEFORE this rent arrives — it
    is only inspected in Step 0 to size the P&I shortfall.
    """

    rent_received: Decimal
    pi_amount: Decimal = Decimal("0")
    checking_balance: Decimal = Decimal("0")
    reserve_debt: Decimal = Decimal("0")
    reserve_bucket_balance: Decimal = Decimal("0")
    reserve_bucket_cap: Decimal = Decimal("0")  # 0 == uncapped
    target_tax_allocation: Decimal = Decimal("0")
    target_reserve_allocation: Decimal = Decimal("0")
    # Already-accrued amounts this cycle — remaining need =
    # max(0, target - already). Lets partial rent payments finish the
    # month without double-allocating tax/reserve on every installment.
    tax_already_allocated: Decimal = Decimal("0")
    reserve_already_allocated: Decimal = Decimal("0")
    chase_reserves: bool = False
    uncollected_reserve_targets: Decimal = Decimal("0")


@dataclass
class StepResult:
    step: int
    name: str
    amount: Decimal
    detail: str = ""


@dataclass
class WaterfallResult:
    steps: List[StepResult] = field(default_factory=list)

    # Step 0
    pi_retained_in_checking: Decimal = Decimal("0.00")
    pi_shortfall: Decimal = Decimal("0.00")

    # Step 1
    reserve_debt_cleared: Decimal = Decimal("0.00")
    new_reserve_debt: Decimal = Decimal("0.00")

    # Aggregate mutations to apply to PropertyStatus
    reserve_balance_delta: Decimal = Decimal("0.00")
    reserve_to_settle_delta: Decimal = Decimal("0.00")
    tax_balance_delta: Decimal = Decimal("0.00")
    tax_to_settle_delta: Decimal = Decimal("0.00")

    # Step 3
    reserve_filled: Decimal = Decimal("0.00")
    pending_overflow: Decimal = Decimal("0.00")  # 'Pending User Overflow Decision'

    # Step 4
    clean_cash_flow: Decimal = Decimal("0.00")

    def as_dict(self) -> dict:
        return {
            "steps": [
                {"step": s.step, "name": s.name, "amount": str(s.amount), "detail": s.detail}
                for s in self.steps
            ],
            "pi_retained_in_checking": str(self.pi_retained_in_checking),
            "pi_shortfall": str(self.pi_shortfall),
            "reserve_debt_cleared": str(self.reserve_debt_cleared),
            "new_reserve_debt": str(self.new_reserve_debt),
            "reserve_balance_delta": str(self.reserve_balance_delta),
            "reserve_to_settle_delta": str(self.reserve_to_settle_delta),
            "tax_balance_delta": str(self.tax_balance_delta),
            "tax_to_settle_delta": str(self.tax_to_settle_delta),
            "reserve_filled": str(self.reserve_filled),
            "pending_overflow": str(self.pending_overflow),
            "clean_cash_flow": str(self.clean_cash_flow),
        }


def run_waterfall(inp: WaterfallInput) -> WaterfallResult:
    """Run the 5-step waterfall over a single rent inflow. Pure/no I/O."""
    res = WaterfallResult()
    available = _money(inp.rent_received)

    # ---- STEP 0: Imminent P&I Provisioning -----------------------------------
    pi_amount = _money(inp.pi_amount)
    checking = _money(inp.checking_balance)
    shortfall = max(Decimal("0.00"), pi_amount - checking)
    pi_retained = min(available, shortfall)
    available -= pi_retained
    res.pi_shortfall = shortfall
    res.pi_retained_in_checking = pi_retained
    res.steps.append(
        StepResult(
            0,
            "Imminent P&I Provisioning",
            pi_retained,
            f"Retained ${pi_retained} in Checking toward ${pi_amount} P&I draft "
            f"(Checking had ${checking}, shortfall ${shortfall}).",
        )
    )

    # ---- STEP 1: Clear Historical Reserve Debt -------------------------------
    reserve_debt = _money(inp.reserve_debt)
    debt_cleared = min(available, reserve_debt)
    available -= debt_cleared
    res.reserve_debt_cleared = debt_cleared
    res.new_reserve_debt = reserve_debt - debt_cleared
    # Restoring the debt lifts the reserve balance AND queues a physical sweep.
    res.reserve_balance_delta += debt_cleared
    res.reserve_to_settle_delta += debt_cleared
    res.steps.append(
        StepResult(
            1,
            "Clear Historical Reserve Debt",
            debt_cleared,
            f"Cleared ${debt_cleared} of reserve_debt (remaining ${res.new_reserve_debt}); "
            f"queued reserve_to_settle += ${debt_cleared}.",
        )
    )

    # ---- STEP 2: Current Month Tax Allocation --------------------------------
    tax_target = max(
        Decimal("0.00"),
        _money(inp.target_tax_allocation) - _money(inp.tax_already_allocated),
    )
    tax_alloc = min(available, tax_target)
    available -= tax_alloc
    res.tax_balance_delta += tax_alloc
    res.tax_to_settle_delta += tax_alloc
    res.steps.append(
        StepResult(
            2,
            "Current Month Tax Allocation",
            tax_alloc,
            f"Accrued ${tax_alloc} to tax_bucket_balance; queued tax_to_settle += ${tax_alloc}.",
        )
    )

    # ---- STEP 3: Current Month Reserve Allocation & Cap Fill -----------------
    reserve_need = max(
        Decimal("0.00"),
        _money(inp.target_reserve_allocation) - _money(inp.reserve_already_allocated),
    )
    if inp.chase_reserves:
        reserve_need += _money(inp.uncollected_reserve_targets)

    desired_deposit = min(available, reserve_need)

    cap = _money(inp.reserve_bucket_cap)
    # Reserve balance at the start of Step 3 already includes the Step-1 debt
    # restoration, so cap room must be measured against that running balance.
    running_reserve = _money(inp.reserve_bucket_balance) + res.reserve_balance_delta

    if cap > 0:
        room_to_cap = max(Decimal("0.00"), cap - running_reserve)
        deposit_to_cap = min(desired_deposit, room_to_cap)
        # Only the slice that was WANTED for reserve but blocked by the cap is
        # paused — never the untargeted surplus (that belongs to Step 4).
        pending = desired_deposit - deposit_to_cap
    else:
        deposit_to_cap = desired_deposit
        pending = Decimal("0.00")

    available -= deposit_to_cap
    # The paused overflow is earmarked (frozen) awaiting the user's A/B/C
    # decision, so it is removed from the cash that flows to Step 4.
    available -= pending

    res.reserve_filled = deposit_to_cap
    res.pending_overflow = pending
    res.reserve_balance_delta += deposit_to_cap
    res.reserve_to_settle_delta += deposit_to_cap
    res.steps.append(
        StepResult(
            3,
            "Current Month Reserve Allocation & Cap Fill",
            deposit_to_cap,
            f"Filled ${deposit_to_cap} toward reserve target ${reserve_need} "
            f"(cap {'$' + str(cap) if cap > 0 else 'none'}); "
            f"paused ${pending} as Pending User Overflow Decision.",
        )
    )

    # ---- STEP 4: Clean Cash Flow ---------------------------------------------
    res.clean_cash_flow = max(Decimal("0.00"), available)
    res.steps.append(
        StepResult(
            4,
            "Clean Cash Flow",
            res.clean_cash_flow,
            f"${res.clean_cash_flow} unencumbered net operating cash remains in Checking.",
        )
    )

    return res
