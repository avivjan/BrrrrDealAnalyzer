/**
 * What a construction account's compact card shows, in plain words (tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md):
 * the money in the account, the lender draws against the lender's budget, the money paid to contractors against the
 * rehab cost, what comes back at the end (or what you must add), and the one thing to do now.
 */
import type { ConstructionAccountStatus } from '../types/constructionAccount'
import { formatMoney } from './money'

export interface AmountOutOfTotal {
  amountDollars: number
  totalDollars: number
  /** 0–100, for a progress bar. */
  percentOfTotal: number
}

export type RehabBudgetDifference =
  | { kind: 'under_budget_you_keep'; dollars: number }
  | { kind: 'over_budget_you_cover'; dollars: number }

export type RehabEndOutcome =
  | { kind: 'back_to_you_at_the_end'; dollars: number }
  | { kind: 'you_need_to_add_now'; dollars: number }

export interface ConstructionAccountUrgentAction {
  label: string
  tone: 'warning' | 'negative'
}

export interface ConstructionAccountSummaryFigures {
  moneyInTheAccountDollars: number | null
  lenderDrawsReceivedOutOfLenderBudget: AmountOutOfTotal
  paidToContractorsOutOfRehabCost: AmountOutOfTotal
  rehabBudgetDifference: RehabBudgetDifference
  rehabEndOutcome: RehabEndOutcome
  urgentAction: ConstructionAccountUrgentAction | null
}

function amountOutOfTotal(amountDollars: number, totalDollars: number): AmountOutOfTotal {
  const percentOfTotal = totalDollars > 0 ? Math.min(100, Math.max(0, (amountDollars / totalDollars) * 100)) : 0
  return { amountDollars, totalDollars, percentOfTotal }
}

/** The budget's spread: positive, the lender's budget is above the rehab cost and you keep the difference. */
export function rehabBudgetDifferenceOf(status: ConstructionAccountStatus): RehabBudgetDifference {
  return status.original_steal_dollars >= 0
    ? { kind: 'under_budget_you_keep', dollars: status.original_steal_dollars }
    : { kind: 'over_budget_you_cover', dollars: -status.original_steal_dollars }
}

/** What the timeline's return row shows: today's projection plus the deposit still to come (it lands in the account). */
export function moneyBackToYouAtTheEndDollars(status: ConstructionAccountStatus): number {
  if (!status.is_linked) return status.rehab_cushion_dollars + Math.max(0, status.original_steal_dollars)
  return Math.max(0, (status.projected_return_at_rehab_end_dollars ?? 0) + (status.remaining_deposit_dollars ?? 0))
}

export function constructionAccountSummaryFiguresOf(status: ConstructionAccountStatus): ConstructionAccountSummaryFigures {
  const topUpNeededDollars = status.top_up_needed_dollars ?? 0
  const remainingDepositDollars = status.remaining_deposit_dollars ?? status.total_to_deposit_dollars
  let urgentAction: ConstructionAccountUrgentAction | null = null
  if (!status.closed_out_at) {
    if (status.needs_attention_because.includes('top_up_needed') && topUpNeededDollars > 0) {
      urgentAction = { label: `Add ${formatMoney(topUpNeededDollars)} now`, tone: 'negative' }
    } else if (status.needs_attention_because.includes('deposit_due') && remainingDepositDollars > 0) {
      urgentAction = { label: `Deposit ${formatMoney(remainingDepositDollars)} due`, tone: 'warning' }
    } else if (status.needs_attention_because.includes('mercury_unavailable')) {
      urgentAction = { label: 'Mercury did not answer', tone: 'warning' }
    }
  }
  return {
    moneyInTheAccountDollars: status.is_linked ? status.current_balance_dollars : null,
    lenderDrawsReceivedOutOfLenderBudget: amountOutOfTotal(status.loan_draws_pulled?.total_dollars ?? 0, status.construction_budget_dollars),
    paidToContractorsOutOfRehabCost: amountOutOfTotal(status.rehab_payments_made?.total_dollars ?? 0, status.rehab_cost_dollars),
    rehabBudgetDifference: rehabBudgetDifferenceOf(status),
    rehabEndOutcome: topUpNeededDollars > 0 && !status.closed_out_at
      ? { kind: 'you_need_to_add_now', dollars: topUpNeededDollars }
      : { kind: 'back_to_you_at_the_end', dollars: moneyBackToYouAtTheEndDollars(status) },
    urgentAction,
  }
}

/** The page's order: accounts needing you first, then live ones, then not linked yet, and closed-out ones last. */
export function constructionAccountDisplayRank(status: ConstructionAccountStatus): number {
  if (status.closed_out_at) return 3
  if (!status.is_linked) return 2
  return status.needs_attention_because.length ? 0 : 1
}
