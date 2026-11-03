/**
 * The "what's next" figures of the liquidity timeline, shown as chips in theater mode
 * (tasks/todo/LiquidityTheaterMode.md, section A): the lowest balance in the next N days and the next open
 * money out / money in. Pure; "today" is passed in.
 */
import type { LiquiditySeries, LiquidityTransaction } from '../types/liquidity'
import { addDays } from './liquidityEngine'

export interface LowestBalanceInWindow {
  balanceDollars: number
  date: string
}

export function lowestBalanceInNextDays(series: LiquiditySeries, todayIsoDate: string, numberOfDays: number): LowestBalanceInWindow | null {
  const lastIsoDate = addDays(todayIsoDate, numberOfDays)
  let lowest: LowestBalanceInWindow | null = null
  for (const day of series.days) {
    if (day.date < todayIsoDate || day.date > lastIsoDate) continue
    if (!lowest || day.balance_dollars < lowest.balanceDollars) lowest = { balanceDollars: day.balance_dollars, date: day.date }
  }
  return lowest
}

/** The earliest open one-off row from today on, money out (amount < 0) or money in (amount > 0). */
export function nextOpenTransaction(transactions: LiquidityTransaction[], todayIsoDate: string, direction: 'money_out' | 'money_in'): LiquidityTransaction | null {
  const candidates = transactions
    .filter(transaction => !transaction.done_at && transaction.effective_date >= todayIsoDate)
    .filter(transaction => (direction === 'money_out' ? transaction.amount_dollars < 0 : transaction.amount_dollars > 0))
    .sort((first, second) => first.effective_date.localeCompare(second.effective_date))
  return candidates[0] ?? null
}
