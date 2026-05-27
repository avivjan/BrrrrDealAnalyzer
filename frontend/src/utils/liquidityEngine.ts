/**
 * Pure computation functions for the liquidity timeline.
 * All amounts are in $k (thousands of dollars).
 * Dates are ISO strings (YYYY-MM-DD) for portability; we parse internally.
 */

import type {
  LiquidityTransaction,
  LiquidityRecurringTransaction,
  DayBucket,
  LiquiditySeries,
  SimulationResult,
} from '../types/liquidity'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Add `days` calendar days to an ISO date string. */
export function addDays(isoDate: string, days: number): string {
  const d = new Date(isoDate + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return toISO(d)
}

/** YYYY-MM-DD from a Date (local). */
export function toISO(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayISO(): string {
  return toISO(new Date())
}

function minStr(a: string, b: string): string {
  return a <= b ? a : b
}

function maxStr(a: string, b: string): string {
  return a >= b ? a : b
}

/** Inclusive day count between two ISO date strings. */
function daysBetween(from: string, to: string): number {
  const a = new Date(from + 'T00:00:00').getTime()
  const b = new Date(to + 'T00:00:00').getTime()
  return Math.round((b - a) / 86_400_000)
}

// ---------------------------------------------------------------------------
// Net-by-day aggregation
// ---------------------------------------------------------------------------

export function aggregateNetByDay(
  transactions: LiquidityTransaction[],
): Map<string, { net_k: number; txns: LiquidityTransaction[] }> {
  const map = new Map<string, { net_k: number; txns: LiquidityTransaction[] }>()
  for (const txn of transactions) {
    const d = txn.effective_date
    const entry = map.get(d)
    if (entry) {
      entry.net_k += txn.amount_k
      entry.txns.push(txn)
    } else {
      map.set(d, { net_k: txn.amount_k, txns: [txn] })
    }
  }
  return map
}

// ---------------------------------------------------------------------------
// Core: build daily liquidity series
// ---------------------------------------------------------------------------

export interface BuildSeriesOptions {
  lookbackDays?: number   // default 90
  horizonMonths?: number  // default 24
  paddingDays?: number    // default 60
}

/**
 * Build the full daily balance series from transactions + opening balance.
 *
 * The series covers every calendar day from `rangeStart` to `rangeEnd`
 * (inclusive), carrying the balance forward on days with zero flow.
 *
 * openingBalanceK is the balance at **start** of openingBalanceDate (before
 * that day's flows). Days before the anchor are flat at openingBalanceK.
 */
export function buildDailyLiquiditySeries(
  transactions: LiquidityTransaction[],
  openingBalanceK: number,
  openingBalanceDate: string,
  rangeStart: string,
  rangeEnd: string,
): LiquiditySeries {
  const netMap = aggregateNetByDay(transactions)

  const totalDays = daysBetween(rangeStart, rangeEnd)
  if (totalDays < 0) {
    return { days: [], globalMin: openingBalanceK, globalMinDates: [openingBalanceDate], firstNegativeDate: null }
  }

  // Build bucket structure
  const days: DayBucket[] = []
  for (let i = 0; i <= totalDays; i++) {
    const date = addDays(rangeStart, i)
    const entry = netMap.get(date)
    days.push({
      date,
      transactions: entry ? entry.txns : [],
      net_k: entry ? entry.net_k : 0,
      balance_k: 0,
    })
  }

  // Fast-forward balance to rangeStart if it's after openingBalanceDate
  let balance = openingBalanceK
  if (rangeStart > openingBalanceDate) {
    const preFlowDates = [...netMap.keys()]
      .filter(d => d > openingBalanceDate && d < rangeStart)
      .sort()
    for (const d of preFlowDates) {
      balance += netMap.get(d)!.net_k
    }
  }

  // Single forward pass: compute balances, track min, track first negative
  let globalMin = Infinity
  let globalMinDates: string[] = []
  let firstNegativeDate: string | null = null

  for (const bucket of days) {
    if (bucket.date < openingBalanceDate) {
      bucket.balance_k = openingBalanceK
    } else if (bucket.date === openingBalanceDate) {
      balance = openingBalanceK + bucket.net_k
      bucket.balance_k = balance
    } else {
      balance += bucket.net_k
      bucket.balance_k = balance
    }

    const b = bucket.balance_k
    if (b < globalMin) {
      globalMin = b
      globalMinDates = [bucket.date]
    } else if (b === globalMin) {
      globalMinDates.push(bucket.date)
    }

    if (b < 0 && firstNegativeDate === null) {
      firstNegativeDate = bucket.date
    }
  }

  if (globalMin === Infinity) {
    globalMin = openingBalanceK
    globalMinDates = [openingBalanceDate]
  }

  return { days, globalMin, globalMinDates, firstNegativeDate }
}

/**
 * Compute default range boundaries from transactions + settings.
 */
export function computeDefaultRange(
  transactions: LiquidityTransaction[],
  openingBalanceDate: string,
  opts: BuildSeriesOptions = {},
): { rangeStart: string; rangeEnd: string } {
  const lookback = opts.lookbackDays ?? 90
  const horizonMonths = opts.horizonMonths ?? 24
  const padding = opts.paddingDays ?? 60
  const today = todayISO()

  let earliest = openingBalanceDate
  let latest = openingBalanceDate
  for (const txn of transactions) {
    if (txn.effective_date < earliest) earliest = txn.effective_date
    if (txn.effective_date > latest) latest = txn.effective_date
  }

  const lookbackDate = addDays(today, -lookback)
  const horizonDate = addDays(today, horizonMonths * 30)
  const paddedEnd = addDays(maxStr(latest, horizonDate), padding)

  return {
    rangeStart: minStr(earliest, lookbackDate),
    rangeEnd: paddedEnd,
  }
}

// ---------------------------------------------------------------------------
// Simulation: impact of a candidate change
// ---------------------------------------------------------------------------

/**
 * Simulate the impact of a candidate transaction change on the liquidity series.
 *
 * `baselineTransactions` = current persisted set (with proposed deletes removed
 *   and proposed edits at their OLD values).
 * `candidateTransactions` = baseline + the candidate change applied.
 */
export function simulateImpact(
  candidateTransactions: LiquidityTransaction[],
  openingBalanceK: number,
  openingBalanceDate: string,
  rangeStart: string,
  rangeEnd: string,
  reserveK: number,
): SimulationResult {
  const series = buildDailyLiquiditySeries(
    candidateTransactions,
    openingBalanceK,
    openingBalanceDate,
    rangeStart,
    rangeEnd,
  )

  const negativeDates: string[] = []
  const reserveBreachDates: string[] = []

  for (const bucket of series.days) {
    if (bucket.balance_k < 0) {
      negativeDates.push(bucket.date)
    }
    if (bucket.balance_k < reserveK && bucket.balance_k >= 0) {
      reserveBreachDates.push(bucket.date)
    }
  }

  return {
    min: series.globalMin,
    minDates: series.globalMinDates,
    firstNegativeDate: series.firstNegativeDate,
    negativeDates,
    breachesReserve: reserveBreachDates.length > 0,
    reserveBreachDates,
  }
}

/**
 * Determine if a candidate change worsens liquidity (requires simulation check).
 * Returns true if: adding an outflow, increasing an outflow, decreasing an inflow,
 * or moving dates in a way that could worsen balances.
 */
export function requiresSimulation(
  oldTxn: LiquidityTransaction | null,
  newAmount_k: number,
  newDate: string,
): boolean {
  if (!oldTxn) {
    // New transaction: only outflows need simulation
    return newAmount_k < 0
  }
  // Edit: simulate if the change could worsen any future balance
  const amountDelta = newAmount_k - oldTxn.amount_k
  if (amountDelta < 0) return true // net decrease
  if (newDate !== oldTxn.effective_date) return true // date moved — could shift balances
  return false
}

// ---------------------------------------------------------------------------
// Recurring transactions: expand a rule into virtual instances
// ---------------------------------------------------------------------------

/** Add `n` calendar months to an ISO date, clamping the day-of-month so
 *  Jan 31 + 1mo == Feb 28 (or 29) rather than rolling into March. */
function addMonthsClamped(isoDate: string, months: number): string {
  const d = new Date(isoDate + 'T00:00:00')
  const targetMonth = d.getMonth() + months
  const targetYear = d.getFullYear() + Math.floor(targetMonth / 12)
  const normalizedMonth = ((targetMonth % 12) + 12) % 12
  const originalDay = d.getDate()
  // Last day of the target month (0th day of next month).
  const lastDay = new Date(targetYear, normalizedMonth + 1, 0).getDate()
  const day = Math.min(originalDay, lastDay)
  return toISO(new Date(targetYear, normalizedMonth, day))
}

/** Step the date by the rule's cadence × the (1-based) occurrence index. */
function dateForOccurrence(
  rule: LiquidityRecurringTransaction,
  index: number,
): string {
  // index 0 returns start_date as-is, so the first event lands exactly on
  // the user-picked start.
  if (index === 0) return rule.start_date
  const interval = Math.max(1, rule.interval || 1)
  switch (rule.frequency) {
    case 'daily':
      return addDays(rule.start_date, index * interval)
    case 'weekly':
      return addDays(rule.start_date, index * 7 * interval)
    case 'biweekly':
      // `biweekly` is sugar for `weekly + interval=2`. We honor the rule's
      // own `interval` on top of that base, so biweekly+interval=2 == every
      // 4 weeks (rare, but lets us treat all frequencies symmetrically).
      return addDays(rule.start_date, index * 14 * interval)
    case 'monthly':
      return addMonthsClamped(rule.start_date, index * interval)
    case 'quarterly':
      return addMonthsClamped(rule.start_date, index * 3 * interval)
    case 'yearly':
      return addMonthsClamped(rule.start_date, index * 12 * interval)
    default:
      // Unreachable while the Literal type holds; keep the timeline robust.
      return rule.start_date
  }
}

/**
 * Expand a recurring rule into virtual transactions falling inside
 * [rangeStart, rangeEnd]. Hard caps:
 *   • rule.end_date (if set)
 *   • rule.occurrences (if set)
 *   • `safetyCap` (defaults to 2000) — defensive ceiling so a malformed
 *     daily-forever rule can't melt the browser.
 *
 * Each virtual instance carries `recurring_rule_id` + `recurring_index`
 * so the UI can edit/delete the source rule and so simulation can treat
 * the projections as real flows.
 */
export function expandRecurringRule(
  rule: LiquidityRecurringTransaction,
  rangeStart: string,
  rangeEnd: string,
  safetyCap = 2000,
): LiquidityTransaction[] {
  if (rule.start_date > rangeEnd) return []

  const out: LiquidityTransaction[] = []
  const maxOccurrences = Math.min(
    rule.occurrences ?? safetyCap,
    safetyCap,
  )

  for (let i = 0; i < maxOccurrences; i++) {
    const date = dateForOccurrence(rule, i)
    if (date > rangeEnd) break
    if (rule.end_date && date > rule.end_date) break
    if (date < rangeStart) continue
    out.push({
      id: `recurring:${rule.id}:${i}`,
      effective_date: date,
      description: rule.description,
      amount_k: rule.amount_k,
      recurring_rule_id: rule.id,
      recurring_index: i,
    })
  }
  return out
}

/** Expand every recurring rule across the current display range. */
export function expandAllRecurringRules(
  rules: LiquidityRecurringTransaction[],
  rangeStart: string,
  rangeEnd: string,
): LiquidityTransaction[] {
  const out: LiquidityTransaction[] = []
  for (const rule of rules) {
    out.push(...expandRecurringRule(rule, rangeStart, rangeEnd))
  }
  return out
}

/** Human-readable cadence summary, used in tooltips and form previews. */
export function describeRecurrence(
  rule: Pick<LiquidityRecurringTransaction, 'frequency' | 'interval'>,
): string {
  const n = Math.max(1, rule.interval || 1)
  const unit = (
    {
      daily: ['day', 'days'],
      weekly: ['week', 'weeks'],
      biweekly: ['2 weeks', '2-week blocks'],
      monthly: ['month', 'months'],
      quarterly: ['quarter', 'quarters'],
      yearly: ['year', 'years'],
    } as const
  )[rule.frequency]
  if (n === 1) return `Every ${unit[0]}`
  return `Every ${n} ${unit[1]}`
}
