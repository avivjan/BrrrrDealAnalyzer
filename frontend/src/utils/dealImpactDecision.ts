/**
 * The decision behind "Import to liquidity" (tasks/todo/DealImpactSimulator.md, B): what the deal (or, on a
 * re-sync, the deal's changes) does to the timeline, as a verdict and a few decision numbers. Pure: the two series,
 * the backend's change list, the reserve and "today" are passed in.
 *
 * "Before" is the timeline as it is now; "after" is the timeline with the deal imported (an import) or with its
 * changes applied (a re-sync). The verdict is returned as text segments, the emphasised ones marked, so the view
 * renders it without HTML.
 */
import type { DealCashRowChange, DealKeyDate, LiquiditySeries } from '../types/liquidity'
import { buildDealImportInsights, type DatedAmount, type DealImportInsights } from './dealCashRowsPreview'
import { formatMoney } from './money'

export type DealImpactMode = 'import' | 'resync'
export type DealImpactRiskLevel = 'stays_above_reserve' | 'dips_below_reserve' | 'goes_negative'
export type DealImpactTone = 'positive' | 'warning' | 'negative'

export interface VerdictSegment {
  text: string
  isEmphasised?: boolean
}

export interface CashNeeded {
  amountDollars: number
  /** The first day the balance would be under the line. */
  neededByDate: string
}

export interface StretchBelowReserve {
  fromDate: string
  toDate: string
  days: number
  /** The stretch runs to the last day of the timeline: no recovery inside it. */
  runsToTheEndOfTheTimeline: boolean
}

export interface DealImpactDecision {
  mode: DealImpactMode
  riskLevel: DealImpactRiskLevel
  tone: DealImpactTone
  alreadyBelowReserveBefore: boolean
  lowestBefore: DatedAmount
  lowestAfter: DatedAmount
  /** after - before: negative = the deal makes the low point lower. */
  lowestChangeDollars: number
  /** Cash that would keep the balance at the reserve / at zero through the low point; null when not needed. */
  cashToKeepTheReserve: CashNeeded | null
  cashToStayAboveZero: CashNeeded | null
  /** The most money the deal has out at once (the deepest running total of its own rows from today), positive. */
  peakCashTiedUp: DatedAmount | null
  daysBelowReserveAfter: number
  daysBelowZeroAfter: number
  longestStretchBelowReserve: StretchBelowReserve | null
  /** The refi: its date and the net of the deal's rows on that day (what it brings back, or still costs). */
  refi: { date: string; netDollarsOnTheDay: number } | null
  /** Back at or above the reserve after the refi: the date and how many days after the refi; null = not in the timeline. */
  backAboveReserveAfterTheRefi: { date: string; daysAfterTheRefi: number } | null
  /** When it never comes back: how far under the reserve the timeline still ends, and its last day. */
  shortOfTheReserveAtTheEnd: DatedAmount | null
  dealMoneyOutDollars: number
  dealMoneyInDollars: number
  dealNetDollars: number
  largestSingleDayOutflow: DatedAmount | null
  next30Days: { cashTodayDollars: number; dealMoneyOutDollars: number; coveredFraction: number }
  insights: DealImportInsights
  verdictHeadline: VerdictSegment[]
  /** The fix ("Bring $X by <date> to keep your reserve"), or a note; null when there is nothing to add. */
  verdictFollowUp: VerdictSegment[] | null
}

/** A re-sync whose low point moves by less than this "barely moves" the timeline. */
export const BARELY_MOVES_THRESHOLD_DOLLARS = 100

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export function formatDecisionDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}, ${year}`
}
function daysBetween(fromIsoDate: string, toIsoDate: string): number {
  return Math.round((Date.parse(`${toIsoDate}T00:00:00Z`) - Date.parse(`${fromIsoDate}T00:00:00Z`)) / 86_400_000)
}
const money = (dollars: number) => formatMoney(Math.round(dollars))
const plainSegment = (text: string): VerdictSegment => ({ text })
const emphasisedSegment = (text: string): VerdictSegment => ({ text, isEmphasised: true })

function longestStretchBelow(series: LiquiditySeries, line: number, todayIsoDate: string): StretchBelowReserve | null {
  const days = series.days.filter(day => day.date >= todayIsoDate)
  let longest: StretchBelowReserve | null = null
  let stretchStart: number | null = null
  for (let index = 0; index <= days.length; index += 1) {
    const isBelow = index < days.length && days[index]!.balance_dollars < line
    if (isBelow && stretchStart === null) stretchStart = index
    if (!isBelow && stretchStart !== null) {
      const stretch = {
        fromDate: days[stretchStart]!.date, toDate: days[index - 1]!.date, days: index - stretchStart,
        runsToTheEndOfTheTimeline: index === days.length,
      }
      if (!longest || stretch.days > longest.days) longest = stretch
      stretchStart = null
    }
  }
  return longest
}

function peakCashTiedUpOf(changes: DealCashRowChange[], todayIsoDate: string): DatedAmount | null {
  const netByDate = new Map<string, number>()
  for (const change of changes) {
    if (change.change_kind === 'removed' || change.change_kind === 'kept_done' || !change.date_after || change.amount_dollars_after === null) continue
    const countedOn = change.date_after < todayIsoDate && change.amount_dollars_after < 0 ? todayIsoDate : change.date_after
    netByDate.set(countedOn, (netByDate.get(countedOn) ?? 0) + change.amount_dollars_after)
  }
  let runningTotal = 0
  let deepest: DatedAmount | null = null
  for (const date of [...netByDate.keys()].sort()) {
    runningTotal += netByDate.get(date)!
    if (runningTotal < 0 && (!deepest || -runningTotal > deepest.amountDollars)) deepest = { date, amountDollars: -runningTotal }
  }
  return deepest
}

export function buildDealImpactDecision(input: {
  seriesBefore: LiquiditySeries
  seriesAfter: LiquiditySeries
  changes: DealCashRowChange[]
  keyDates?: DealKeyDate[]
  reserveDollars: number
  todayIsoDate: string
  mode: DealImpactMode
}): DealImpactDecision {
  const { seriesBefore, seriesAfter, changes, reserveDollars, todayIsoDate, mode } = input
  const insights = buildDealImportInsights(seriesBefore, seriesAfter, changes, reserveDollars, todayIsoDate)
  const lowestBefore = insights.lowestBalanceWithoutTheDeal
  const lowestAfter = insights.lowestBalanceWithTheDeal
  const riskLevel: DealImpactRiskLevel = lowestAfter.amountDollars < 0 ? 'goes_negative'
    : lowestAfter.amountDollars < reserveDollars ? 'dips_below_reserve' : 'stays_above_reserve'
  const tone: DealImpactTone = riskLevel === 'goes_negative' ? 'negative' : riskLevel === 'dips_below_reserve' ? 'warning' : 'positive'

  const daysFromToday = seriesAfter.days.filter(day => day.date >= todayIsoDate)
  const daysBelowZeroAfter = daysFromToday.filter(day => day.balance_dollars < 0).length
  const cashToKeepTheReserve = lowestAfter.amountDollars < reserveDollars && insights.firstDateBelowReserveWithTheDeal
    ? { amountDollars: reserveDollars - lowestAfter.amountDollars, neededByDate: insights.firstDateBelowReserveWithTheDeal } : null
  const cashToStayAboveZero = lowestAfter.amountDollars < 0 && insights.firstNegativeDateWithTheDeal
    ? { amountDollars: -lowestAfter.amountDollars, neededByDate: insights.firstNegativeDateWithTheDeal } : null

  const refiDate = input.keyDates?.find(keyDate => keyDate.key === 'refi_closed')?.date ?? insights.lastDealRowDate
  const refi = refiDate ? {
    date: refiDate,
    netDollarsOnTheDay: changes
      .filter(change => change.change_kind !== 'removed' && change.change_kind !== 'kept_done' && change.date_after === refiDate)
      .reduce((total, change) => total + (change.amount_dollars_after ?? 0), 0),
  } : null
  // "Back above" only means something if the balance went under the reserve before (or on) the refi.
  const wasUnderTheReserveUntilTheRefi = !!refiDate && daysFromToday.some(day => day.date <= refiDate && day.balance_dollars < reserveDollars)
  const backDay = refiDate && wasUnderTheReserveUntilTheRefi
    ? daysFromToday.find(day => day.date >= refiDate && day.balance_dollars >= reserveDollars) : undefined
  const backAboveReserveAfterTheRefi = backDay && refiDate ? { date: backDay.date, daysAfterTheRefi: daysBetween(refiDate, backDay.date) } : null
  const lastDay = seriesAfter.days[seriesAfter.days.length - 1]
  const shortOfTheReserveAtTheEnd = !backAboveReserveAfterTheRefi && lastDay && lastDay.balance_dollars < reserveDollars
    ? { date: lastDay.date, amountDollars: reserveDollars - lastDay.balance_dollars } : null

  const decisionWithoutWords = {
    mode, riskLevel, tone,
    alreadyBelowReserveBefore: lowestBefore.amountDollars < reserveDollars,
    lowestBefore, lowestAfter,
    lowestChangeDollars: lowestAfter.amountDollars - lowestBefore.amountDollars,
    cashToKeepTheReserve, cashToStayAboveZero,
    peakCashTiedUp: peakCashTiedUpOf(changes, todayIsoDate),
    daysBelowReserveAfter: insights.daysBelowReserveWithTheDeal,
    daysBelowZeroAfter,
    longestStretchBelowReserve: longestStretchBelow(seriesAfter, reserveDollars, todayIsoDate),
    refi, backAboveReserveAfterTheRefi, shortOfTheReserveAtTheEnd,
    dealMoneyOutDollars: insights.dealMoneyOutDollars,
    dealMoneyInDollars: insights.dealMoneyInDollars,
    dealNetDollars: insights.dealMoneyInDollars - insights.dealMoneyOutDollars,
    largestSingleDayOutflow: insights.largestSingleDayOutflowOfTheDeal,
    next30Days: {
      cashTodayDollars: insights.cashTodayDollars,
      dealMoneyOutDollars: insights.dealMoneyOutInTheNext30DaysDollars,
      coveredFraction: insights.dealMoneyOutInTheNext30DaysDollars > 0
        ? Math.max(0, Math.min(1, insights.cashTodayDollars / insights.dealMoneyOutInTheNext30DaysDollars)) : 1,
    },
    insights,
  }
  return { ...decisionWithoutWords, ...verdictWords(decisionWithoutWords, reserveDollars) }
}

type DecisionWithoutWords = Omit<DealImpactDecision, 'verdictHeadline' | 'verdictFollowUp'>

/** The verdict sentence, worded for an import (a new deal) or a re-sync (applying a deal's changes). */
function verdictWords(decision: DecisionWithoutWords, reserveDollars: number): Pick<DealImpactDecision, 'verdictHeadline' | 'verdictFollowUp'> {
  const { mode, riskLevel, lowestAfter, lowestBefore, lowestChangeDollars } = decision
  const subject = mode === 'import' ? 'This deal' : 'Applying these changes'
  const recoveryTail: VerdictSegment[] = decision.backAboveReserveAfterTheRefi
    ? [plainSegment(', and the refi brings you back above your reserve by '), emphasisedSegment(formatDecisionDate(decision.backAboveReserveAfterTheRefi.date)), plainSegment('.')]
    : [plainSegment(", and you don't recover in the timeline.")]

  let verdictHeadline: VerdictSegment[]
  if (riskLevel === 'goes_negative') {
    verdictHeadline = [plainSegment(`${subject} takes you `), emphasisedSegment(`${money(-lowestAfter.amountDollars)} below zero`),
      plainSegment(' on '), emphasisedSegment(formatDecisionDate(lowestAfter.date)), ...recoveryTail]
  } else if (riskLevel === 'dips_below_reserve') {
    const stretchDays = decision.daysBelowReserveAfter
    verdictHeadline = [plainSegment(mode === 'import' ? "You'd be under your " : `${subject} puts you under your `),
      plainSegment(`${money(reserveDollars)} reserve for `), emphasisedSegment(`${stretchDays} day${stretchDays === 1 ? '' : 's'}`),
      plainSegment(' (lowest '), emphasisedSegment(money(lowestAfter.amountDollars)), plainSegment(` on ${formatDecisionDate(lowestAfter.date)})`),
      ...(decision.backAboveReserveAfterTheRefi ? recoveryTail : [plainSegment('.')])]
  } else if (mode === 'resync' && Math.abs(lowestChangeDollars) < BARELY_MOVES_THRESHOLD_DOLLARS) {
    verdictHeadline = [plainSegment('These changes barely move your timeline (lowest '), emphasisedSegment(money(lowestBefore.amountDollars)),
      plainSegment(' → '), emphasisedSegment(money(lowestAfter.amountDollars)), plainSegment(').')]
  } else if (mode === 'resync' && lowestChangeDollars > 0) {
    verdictHeadline = [plainSegment('These changes improve your lowest point by '), emphasisedSegment(money(lowestChangeDollars)),
      plainSegment(' (to '), emphasisedSegment(money(lowestAfter.amountDollars)), plainSegment(` on ${formatDecisionDate(lowestAfter.date)}).`)]
  } else {
    verdictHeadline = [plainSegment(mode === 'import' ? 'You stay above your ' : `${subject} keeps you above your `),
      plainSegment(`${money(reserveDollars)} reserve: lowest `), emphasisedSegment(money(lowestAfter.amountDollars)),
      plainSegment(' on '), emphasisedSegment(formatDecisionDate(lowestAfter.date)), plainSegment('.')]
  }

  let verdictFollowUp: VerdictSegment[] | null = null
  if (decision.cashToKeepTheReserve) {
    verdictFollowUp = [plainSegment('Bring '), emphasisedSegment(money(decision.cashToKeepTheReserve.amountDollars)),
      plainSegment(' by '), emphasisedSegment(formatDecisionDate(decision.cashToKeepTheReserve.neededByDate)), plainSegment(' to keep your reserve')]
    if (decision.cashToStayAboveZero) verdictFollowUp.push(plainSegment(` (${money(decision.cashToStayAboveZero.amountDollars)} just to stay above zero)`))
    verdictFollowUp.push(plainSegment('.'))
  }
  if (decision.alreadyBelowReserveBefore) {
    const note = plainSegment(mode === 'import'
      ? 'Your timeline is already under the reserve without this deal.'
      : 'Your timeline is already under the reserve before these changes.')
    verdictFollowUp = verdictFollowUp ? [...verdictFollowUp, plainSegment(' '), note] : [note]
  }
  return { verdictHeadline, verdictFollowUp }
}
