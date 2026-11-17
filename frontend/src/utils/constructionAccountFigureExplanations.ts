/**
 * "Why this number" for the compact construction-account card (tasks/todo/ConstructionAccountCardExplanations.md):
 * "Back to you at the end" and "Safe to take out now", each as a plain sentence and the calculation, line by line.
 *
 * Built from the same status fields and the same formulas as the backend projection
 * (`BackEnd/BL/liquidity/constructionAccount/construction_account_projection.py`), so the lines always add up to the
 * figure the card shows.
 */
import type { ConstructionAccountStatus } from '../types/constructionAccount'
import { moneyBackToYouAtTheEndDollars } from './constructionAccountSummaryFigures'
import { formatMoney } from './money'

export interface FigureExplanationLine {
  /** How the line enters the calculation: the first amount, added, taken away, or the result. */
  operation: 'start' | 'plus' | 'minus' | 'result'
  label: string
  amountDollars: number
  /** Where the amount comes from, e.g. "$73,000 budget − $52,900 received". */
  detail?: string
}

export interface FigureExplanation {
  summary: string
  lines: FigureExplanationLine[]
  /** One more sentence under the calculation (what limits it, what it is made of). */
  footnote?: string
}

const SAFE_TO_TAKE_OUT_LIMIT_SENTENCES = {
  available_balance: 'Limited by what is in the account right now.',
  buffer_to_keep: 'Limited by the buffer you keep in the account.',
  projected_return: 'Limited by what the account will give back at the end: taking more now would leave the rest of the rehab short.',
} as const

export function backToYouAtTheEndExplanation(status: ConstructionAccountStatus): FigureExplanation {
  if (!status.is_linked) {
    const keptUnderBudgetDollars = Math.max(0, status.original_steal_dollars)
    return {
      summary: 'No construction account yet, so this is the plan: what you deposit comes back, and so does what the lender pays beyond the rehab cost.',
      lines: [
        { operation: 'start', label: 'Your deposit (cushion)', amountDollars: status.rehab_cushion_dollars },
        { operation: 'plus', label: 'Under budget: you keep', amountDollars: keptUnderBudgetDollars,
          detail: `${formatMoney(status.construction_budget_dollars)} budget − ${formatMoney(status.rehab_cost_dollars)} rehab` },
        { operation: 'result', label: 'Back to you at the end', amountDollars: moneyBackToYouAtTheEndDollars(status) },
      ],
    }
  }
  const drawsReceivedDollars = status.loan_draws_pulled?.total_dollars ?? 0
  const paidToContractorsDollars = status.rehab_payments_made?.total_dollars ?? 0
  const remainingDepositDollars = status.remaining_deposit_dollars ?? 0
  const projectedReturnDollars = status.projected_return_at_rehab_end_dollars ?? 0
  const returnAfterTheRemainingDepositDollars = projectedReturnDollars + remainingDepositDollars
  const lines: FigureExplanationLine[] = [
    { operation: 'start', label: 'In the account now', amountDollars: status.current_balance_dollars ?? 0 },
    { operation: 'plus', label: 'Lender draws still to come', amountDollars: status.loan_draws_remaining_to_pull_dollars ?? 0,
      detail: `${formatMoney(status.construction_budget_dollars)} budget − ${formatMoney(drawsReceivedDollars)} received` },
    { operation: 'minus', label: 'Rehab still to pay', amountDollars: status.unpaid_rehab_remaining_dollars ?? 0,
      detail: `${formatMoney(status.rehab_cost_dollars)} rehab − ${formatMoney(paidToContractorsDollars)} paid` },
  ]
  if (remainingDepositDollars > 0) {
    lines.push({ operation: 'plus', label: 'The deposit you still owe', amountDollars: remainingDepositDollars, detail: 'it lands in the account, so it comes back too' })
  }
  if (returnAfterTheRemainingDepositDollars < 0) {
    lines.push({ operation: 'result', label: 'Short: you need to add now', amountDollars: -returnAfterTheRemainingDepositDollars })
    return {
      summary: 'What is in the account plus the draws still to come does not cover the rehab still to pay.',
      lines,
      footnote: 'Add the shortfall (a top-up) so the contractors can be paid; nothing comes back until then.',
    }
  }
  lines.push({ operation: 'result', label: status.closed_out_at ? 'Came back to you' : 'Back to you at the end', amountDollars: moneyBackToYouAtTheEndDollars(status) })
  const ownMoneyBackDollars = (status.own_money_back_at_rehab_end_dollars ?? 0) + remainingDepositDollars
  return {
    summary: status.closed_out_at
      ? 'The account was closed out: what was left in it came back to you.'
      : 'When the rehab ends and the lender has paid every draw, this is what is left in the account for you.',
    lines,
    footnote: `Of it: your own money ${formatMoney(ownMoneyBackDollars)}, and the budget spread ${formatMoney(status.spread_at_rehab_end_dollars ?? 0)}.`,
  }
}

export function safeToTakeOutNowExplanation(status: ConstructionAccountStatus): FigureExplanation {
  if (status.closed_out_at) {
    return { summary: 'The account is closed out: there is nothing more to take out.', lines: [
      { operation: 'result', label: 'Safe to take out now', amountDollars: 0 },
    ] }
  }
  const availableDollars = status.available_balance_dollars ?? 0
  const bufferToKeepDollars = status.minimum_balance_to_keep_in_construction_account_dollars ?? 0
  const freeNowDollars = availableDollars - bufferToKeepDollars
  const projectedReturnDollars = status.projected_return_at_rehab_end_dollars ?? 0
  const lines: FigureExplanationLine[] = [
    { operation: 'start', label: 'Available in the account', amountDollars: availableDollars },
  ]
  if (bufferToKeepDollars > 0) {
    lines.push({ operation: 'minus', label: 'Always keep in the account', amountDollars: bufferToKeepDollars, detail: 'your buffer for bills the lender reimburses later' })
    lines.push({ operation: 'result', label: 'Free now', amountDollars: freeNowDollars })
  }
  lines.push({ operation: 'start', label: 'What the account gives back at the end', amountDollars: projectedReturnDollars,
    detail: 'in the account + draws still to come − rehab still to pay' })
  lines.push({ operation: 'result', label: 'Safe to take out now (the smaller of the two)', amountDollars: status.safe_to_steal_now_dollars ?? 0 })
  return {
    summary: 'What you can move to checking now (a steal) without leaving the rehab short: the smaller of what is free in the account today and what it will give back at the end.',
    lines,
    footnote: status.safe_to_steal_now_is_capped_by ? SAFE_TO_TAKE_OUT_LIMIT_SENTENCES[status.safe_to_steal_now_is_capped_by] : undefined,
  }
}
