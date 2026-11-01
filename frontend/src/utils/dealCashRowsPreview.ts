/**
 * The import preview of a BRRRR deal (tasks/todo/DealCashInLiquidity.md, decision 11): the timeline "with this deal"
 * built from the backend's before -> after list, and the insights shown before importing. Pure: "today" and the
 * series are passed in.
 */
import type { DealCashRowChange, LiquiditySeries, LiquidityTransaction } from '../types/liquidity'

/** The one-off transactions as they would be after the changes: the deal's rows replaced, every other row untouched. */
export function transactionsAfterDealChanges(
  transactions: LiquidityTransaction[],
  changes: DealCashRowChange[],
): LiquidityTransaction[] {
  const changeByTransactionId = new Map(changes.filter(change => change.transaction_id).map(change => [change.transaction_id!, change]))
  const transactionsAfter: LiquidityTransaction[] = []
  for (const transaction of transactions) {
    const change = changeByTransactionId.get(transaction.id)
    if (!change || change.change_kind === 'kept_done') {
      transactionsAfter.push(transaction)
    } else if (change.change_kind !== 'removed' && change.date_after && change.amount_dollars_after !== null) {
      transactionsAfter.push({ ...transaction, effective_date: change.date_after, amount_dollars: change.amount_dollars_after, description: change.description })
    }
  }
  for (const change of changes) {
    if (change.change_kind !== 'added' || !change.date_after || change.amount_dollars_after === null) continue
    transactionsAfter.push({
      id: `preview-${change.item_key}-${change.occurrence_number}`,
      effective_date: change.date_after,
      description: change.description,
      amount_dollars: change.amount_dollars_after,
      done_at: null,
      source_item_key: change.item_key,
      source_occurrence_number: change.occurrence_number,
      created_because_refi_is_late: change.created_because_refi_is_late,
    })
  }
  return transactionsAfter
}

export interface DatedAmount {
  date: string
  amountDollars: number
}

export interface DealRowsInMonth {
  /** YYYY-MM */
  month: string
  rowCount: number
  netDollars: number
}

export interface DealImportInsights {
  lowestBalanceWithoutTheDeal: DatedAmount
  lowestBalanceWithTheDeal: DatedAmount
  /** Days from today on with the balance under the reserve (with the deal), and the first one. */
  daysBelowReserveWithTheDeal: number
  firstDateBelowReserveWithTheDeal: string | null
  firstNegativeDateWithTheDeal: string | null
  dealMoneyOutDollars: number
  dealMoneyInDollars: number
  largestSingleDayOutflowOfTheDeal: DatedAmount | null
  cashTodayDollars: number
  dealMoneyOutInTheNext30DaysDollars: number
  /** The deal's last row (the refi), and the first day after it with the balance back at or above the reserve. */
  lastDealRowDate: string | null
  dateBackAtOrAboveReserveAfterTheLastDealRow: string | null
  dealRowsByMonth: DealRowsInMonth[]
}

function addDaysToIsoDate(isoDate: string, days: number): string {
  const day = new Date(`${isoDate}T00:00:00Z`)
  day.setUTCDate(day.getUTCDate() + days)
  return day.toISOString().slice(0, 10)
}

function lowestBalanceFromToday(series: LiquiditySeries, todayIsoDate: string): DatedAmount {
  let lowest: DatedAmount | null = null
  for (const day of series.days) {
    if (day.date < todayIsoDate) continue
    if (!lowest || day.balance_dollars < lowest.amountDollars) lowest = { date: day.date, amountDollars: day.balance_dollars }
  }
  return lowest ?? { date: todayIsoDate, amountDollars: series.globalMin }
}

/**
 * `seriesWithoutTheDeal` / `seriesWithTheDeal` are the daily balances (same range) before and after the changes;
 * `changes` is the backend's list. Only the deal's rows that still move money (not removed, not done) count as the deal.
 */
export function buildDealImportInsights(
  seriesWithoutTheDeal: LiquiditySeries,
  seriesWithTheDeal: LiquiditySeries,
  changes: DealCashRowChange[],
  reserveDollars: number,
  todayIsoDate: string,
): DealImportInsights {
  const dealRowsThatMoveMoney = changes.filter(change =>
    change.change_kind !== 'removed' && change.change_kind !== 'kept_done' && change.date_after && change.amount_dollars_after !== null)

  const netDollarsByDate = new Map<string, number>()
  const rowsByMonth = new Map<string, DealRowsInMonth>()
  let dealMoneyOutDollars = 0
  let dealMoneyInDollars = 0
  let dealMoneyOutInTheNext30DaysDollars = 0
  const thirtyDaysFromToday = addDaysToIsoDate(todayIsoDate, 30)
  for (const row of dealRowsThatMoveMoney) {
    const amount = row.amount_dollars_after!
    const countedOnDate = row.date_after! < todayIsoDate && amount < 0 ? todayIsoDate : row.date_after!
    netDollarsByDate.set(countedOnDate, (netDollarsByDate.get(countedOnDate) ?? 0) + amount)
    if (amount < 0) {
      dealMoneyOutDollars += -amount
      if (countedOnDate <= thirtyDaysFromToday) dealMoneyOutInTheNext30DaysDollars += -amount
    } else {
      dealMoneyInDollars += amount
    }
    const month = row.date_after!.slice(0, 7)
    const monthTotals = rowsByMonth.get(month) ?? { month, rowCount: 0, netDollars: 0 }
    monthTotals.rowCount += 1
    monthTotals.netDollars += amount
    rowsByMonth.set(month, monthTotals)
  }

  let largestSingleDayOutflowOfTheDeal: DatedAmount | null = null
  for (const [date, netDollars] of netDollarsByDate) {
    if (netDollars < 0 && (!largestSingleDayOutflowOfTheDeal || -netDollars > largestSingleDayOutflowOfTheDeal.amountDollars)) {
      largestSingleDayOutflowOfTheDeal = { date, amountDollars: -netDollars }
    }
  }

  const daysFromTodayWithTheDeal = seriesWithTheDeal.days.filter(day => day.date >= todayIsoDate)
  const daysBelowReserve = daysFromTodayWithTheDeal.filter(day => day.balance_dollars < reserveDollars)
  const lastDealRowDate = dealRowsThatMoveMoney.reduce<string | null>(
    (latest, row) => (latest === null || row.date_after! > latest ? row.date_after! : latest), null)
  const dayBackAtOrAboveReserve = lastDealRowDate === null ? undefined
    : daysFromTodayWithTheDeal.find(day => day.date > lastDealRowDate && day.balance_dollars >= reserveDollars)
  const todayWithoutTheDeal = seriesWithoutTheDeal.days.find(day => day.date === todayIsoDate)

  return {
    lowestBalanceWithoutTheDeal: lowestBalanceFromToday(seriesWithoutTheDeal, todayIsoDate),
    lowestBalanceWithTheDeal: lowestBalanceFromToday(seriesWithTheDeal, todayIsoDate),
    daysBelowReserveWithTheDeal: daysBelowReserve.length,
    firstDateBelowReserveWithTheDeal: daysBelowReserve[0]?.date ?? null,
    firstNegativeDateWithTheDeal: daysFromTodayWithTheDeal.find(day => day.balance_dollars < 0)?.date ?? null,
    dealMoneyOutDollars,
    dealMoneyInDollars,
    largestSingleDayOutflowOfTheDeal,
    cashTodayDollars: todayWithoutTheDeal?.balance_dollars ?? 0,
    dealMoneyOutInTheNext30DaysDollars,
    lastDealRowDate,
    dateBackAtOrAboveReserveAfterTheLastDealRow: dayBackAtOrAboveReserve?.date ?? null,
    dealRowsByMonth: [...rowsByMonth.values()].sort((first, second) => first.month.localeCompare(second.month)),
  }
}
