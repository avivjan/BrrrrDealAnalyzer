/**
 * A deal's whole story for the legend's Transactions (tasks/todo/LiquidityDealTransactionsAndHmlMonthlyInterest.md,
 * B): its key dates (the Cash Needed table's markers) and every one of its rows, open and done, in date order and
 * grouped by month with each month's count, net and done count. A key date comes first on its day. Pure.
 */
import type { DealKeyDate, DealMilestoneState, LiquidityTransaction } from '../../../types/liquidity'
import { dealKeyOfTransaction } from '../dealColors'

export type DealTimelineItem =
  | { kind: 'key_date'; date: string; keyDate: DealKeyDate; milestoneState: DealMilestoneState | null }
  | { kind: 'transaction'; date: string; transaction: LiquidityTransaction }

export interface DealTimelineMonth {
  /** "2026-12" */
  monthKey: string
  /** "Dec 2026" */
  monthLabel: string
  items: DealTimelineItem[]
  transactionCount: number
  doneTransactionCount: number
  /** The net of every row in the month, open and done. */
  netDollars: number
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function monthLabelOf(monthKey: string): string {
  const [year, monthNumber] = monthKey.split('-')
  return `${MONTH_NAMES[Number(monthNumber) - 1] ?? ''} ${year}`
}

export function dealTimelineByMonth(
  transactions: LiquidityTransaction[],
  dealKey: string,
  keyDates: DealKeyDate[],
  milestones: DealMilestoneState[],
): DealTimelineMonth[] {
  const milestoneStateByKey = new Map(milestones.map(state => [state.milestone as string, state]))
  const keyDateItems: DealTimelineItem[] = keyDates.map(keyDate => ({
    kind: 'key_date', date: keyDate.date, keyDate, milestoneState: milestoneStateByKey.get(keyDate.key) ?? null,
  }))
  const transactionItems: DealTimelineItem[] = transactions
    .filter(transaction => dealKeyOfTransaction(transaction) === dealKey)
    .sort((first, second) => first.effective_date.localeCompare(second.effective_date)
      || (first.sequence_within_day ?? 0) - (second.sequence_within_day ?? 0))
    .map(transaction => ({ kind: 'transaction', date: transaction.effective_date, transaction }))
  // Stable sort: on a shared day the key dates (listed first) stay first, each list keeps its own order.
  const items = [...keyDateItems, ...transactionItems].sort((first, second) => first.date.localeCompare(second.date)
    || (first.kind === second.kind ? 0 : first.kind === 'key_date' ? -1 : 1))

  const months: DealTimelineMonth[] = []
  for (const item of items) {
    const monthKey = item.date.slice(0, 7)
    let month = months[months.length - 1]
    if (!month || month.monthKey !== monthKey) {
      month = { monthKey, monthLabel: monthLabelOf(monthKey), items: [], transactionCount: 0, doneTransactionCount: 0, netDollars: 0 }
      months.push(month)
    }
    month.items.push(item)
    if (item.kind === 'transaction') {
      month.transactionCount += 1
      if (item.transaction.done_at) month.doneTransactionCount += 1
      month.netDollars += item.transaction.amount_dollars
    }
  }
  return months
}

/** The month the Transactions open on: this month if the deal has anything in it, else the first month with an open row, else the first. */
/**
 * A recurring rule's recent occurrences for the legend: every one from its overdue-from date up to today (done,
 * overdue or moved), then the next `upcomingCount`, in date order. History is left out.
 */
export function recentOccurrencesOfRule(occurrences: LiquidityTransaction[], ruleId: string, todayIsoDate: string, upcomingCount = 2): LiquidityTransaction[] {
  const ofTheRule = occurrences
    .filter(occurrence => occurrence.recurring_rule_id === ruleId && !occurrence.recurring_is_history)
    .sort((first, second) => (first.recurring_scheduled_date ?? first.effective_date).localeCompare(second.recurring_scheduled_date ?? second.effective_date))
  const pastOrToday = ofTheRule.filter(occurrence => (occurrence.recurring_scheduled_date ?? occurrence.effective_date) <= todayIsoDate)
  const upcoming = ofTheRule.filter(occurrence => (occurrence.recurring_scheduled_date ?? occurrence.effective_date) > todayIsoDate).slice(0, upcomingCount)
  return [...pastOrToday, ...upcoming]
}

export function monthToOpenFirst(months: DealTimelineMonth[], todayIsoDate: string): string | null {
  const thisMonthKey = todayIsoDate.slice(0, 7)
  if (months.some(month => month.monthKey === thisMonthKey)) return thisMonthKey
  const firstMonthWithAnOpenRow = months.find(month => month.items.some(item => item.kind === 'transaction' && !item.transaction.done_at))
  return firstMonthWithAnOpenRow?.monthKey ?? months[0]?.monthKey ?? null
}

/** The rows of a day that are marked done, one-off rows and recurring occurrences (the day modal's "Done on this day"). */
export function doneTransactionsOnDate(transactions: LiquidityTransaction[], isoDate: string): LiquidityTransaction[] {
  return transactions
    .filter(transaction => !!transaction.done_at && !transaction.recurring_is_history && transaction.effective_date === isoDate)
    .sort((first, second) => (first.sequence_within_day ?? 0) - (second.sequence_within_day ?? 0))
}
