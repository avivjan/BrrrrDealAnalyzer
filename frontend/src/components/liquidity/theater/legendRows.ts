/**
 * A deal's open rows for the legend, month by month (tasks/todo/LiquidityTheaterOnly.md, section 3): every row
 * not marked done, in date order, grouped under a month with its row count and net. Pure.
 */
import type { LiquidityTransaction } from '../../../types/liquidity'
import { dealKeyOfTransaction } from '../dealColors'

export interface OpenRowsOfOneMonth {
  /** "2026-12" */
  monthKey: string
  /** "Dec 2026" */
  monthLabel: string
  rows: LiquidityTransaction[]
  netDollars: number
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function groupOpenRowsOfDealByMonth(transactions: LiquidityTransaction[], dealKey: string): OpenRowsOfOneMonth[] {
  const openRowsOfTheDeal = transactions
    .filter(transaction => !transaction.done_at && dealKeyOfTransaction(transaction) === dealKey)
    .sort((first, second) => first.effective_date.localeCompare(second.effective_date)
      || (first.sequence_within_day ?? 0) - (second.sequence_within_day ?? 0))
  const months: OpenRowsOfOneMonth[] = []
  for (const transaction of openRowsOfTheDeal) {
    const monthKey = transaction.effective_date.slice(0, 7)
    let month = months[months.length - 1]
    if (!month || month.monthKey !== monthKey) {
      const [year, monthNumber] = monthKey.split('-')
      month = { monthKey, monthLabel: `${MONTH_NAMES[Number(monthNumber) - 1] ?? ''} ${year}`, rows: [], netDollars: 0 }
      months.push(month)
    }
    month.rows.push(transaction)
    month.netDollars += transaction.amount_dollars
  }
  return months
}
