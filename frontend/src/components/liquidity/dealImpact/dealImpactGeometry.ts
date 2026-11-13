/**
 * Pure geometry for the deal impact chart (tasks/todo/DealImpactSimulator.md, A): which days a range chip shows, the
 * x and y scales of a chart fitted to its width (no scrolling), the gap between the two lines, the runs where the
 * projected balance is under a line, and label stacking so the flags never overlap. No DOM, no colours.
 */
import type { Point } from '../chart/geometry'

export type DealImpactRange = 'deal_lifecycle' | 'until_last_deal_ends' | 'six_months' | 'one_year' | 'all'

export const DEAL_IMPACT_RANGES: { key: DealImpactRange; label: string }[] = [
  { key: 'deal_lifecycle', label: 'Deal lifecycle' },
  { key: 'until_last_deal_ends', label: 'Until last deal ends' },
  { key: 'six_months', label: '6 months' },
  { key: 'one_year', label: '1 year' },
  { key: 'all', label: 'All' },
]

export interface IndexWindow {
  first: number
  last: number
}

function addDays(isoDate: string, days: number): string {
  const day = new Date(`${isoDate}T00:00:00Z`)
  day.setUTCDate(day.getUTCDate() + days)
  return day.toISOString().slice(0, 10)
}

function firstIndexOnOrAfter(dates: readonly string[], isoDate: string): number {
  const index = dates.findIndex(date => date >= isoDate)
  return index < 0 ? dates.length - 1 : index
}

function lastIndexOnOrBefore(dates: readonly string[], isoDate: string): number {
  for (let index = dates.length - 1; index >= 0; index -= 1) if (dates[index]! <= isoDate) return index
  return 0
}

/**
 * The days a range shows. "Deal lifecycle": a week before today through 60 days after the refi (or 30 after the low
 * point, or 60 after today, whichever is latest). "Until last deal ends": a week before today through the latest refi
 * among the deals in the timeline and the incoming one (tasks/todo/ConstructionAccountPerRehab.md, Step G); without
 * one, as "Deal lifecycle". The fixed ranges start a week before today. Always inside the series.
 */
export function windowForRange(
  dates: readonly string[],
  range: DealImpactRange,
  todayIsoDate: string,
  milestones: { refiDate: string | null; lowestDate: string | null; lastDealEndDate?: string | null },
): IndexWindow {
  if (dates.length === 0) return { first: 0, last: -1 }
  if (range === 'all') return { first: 0, last: dates.length - 1 }
  const startDate = addDays(todayIsoDate, -7)
  let endDate: string
  if (range === 'six_months') endDate = addDays(todayIsoDate, 183)
  else if (range === 'one_year') endDate = addDays(todayIsoDate, 365)
  else if (range === 'until_last_deal_ends' && milestones.lastDealEndDate) endDate = milestones.lastDealEndDate
  else {
    const candidates = [addDays(todayIsoDate, 60)]
    if (milestones.refiDate) candidates.push(addDays(milestones.refiDate, 60))
    if (milestones.lowestDate) candidates.push(addDays(milestones.lowestDate, 30))
    endDate = candidates.sort()[candidates.length - 1]!
  }
  const first = firstIndexOnOrAfter(dates, startDate)
  const last = Math.max(first, lastIndexOnOrBefore(dates, endDate))
  return { first, last }
}

export interface PlotBox {
  left: number
  right: number
  top: number
  bottom: number
}

/** x of a day index, the window spread evenly over the plot's width. */
export function xForWindowIndex(index: number, window: IndexWindow, box: PlotBox): number {
  const span = Math.max(1, window.last - window.first)
  return box.left + ((index - window.first) / span) * (box.right - box.left)
}

/** The day index under an x, clamped to the window. */
export function windowIndexForX(x: number, window: IndexWindow, box: PlotBox): number {
  const span = Math.max(1, window.last - window.first)
  const fraction = (x - box.left) / Math.max(1, box.right - box.left)
  return Math.min(window.last, Math.max(window.first, Math.round(window.first + fraction * span)))
}

export interface ValueRange {
  min: number
  max: number
}

/** The y range over both lines in the window, always including zero and the reserve, with 8% room. */
export function valueRangeFor(balancesBefore: readonly number[], balancesAfter: readonly number[], window: IndexWindow, reserveDollars: number): ValueRange {
  let min = Math.min(0, reserveDollars)
  let max = Math.max(0, reserveDollars)
  for (let index = window.first; index <= window.last; index += 1) {
    for (const value of [balancesBefore[index], balancesAfter[index]]) {
      if (value === undefined) continue
      if (value < min) min = value
      if (value > max) max = value
    }
  }
  const room = Math.max((max - min) * 0.08, 500)
  return { min: min - room, max: max + room }
}

export function yForValue(value: number, range: ValueRange, box: PlotBox): number {
  const span = Math.max(1, range.max - range.min)
  return box.bottom - ((value - range.min) / span) * (box.bottom - box.top)
}

/** The area between the two lines: along "after", then back along "before". */
export function gapPolygonPath(pointsBefore: readonly Point[], pointsAfter: readonly Point[]): string {
  if (pointsAfter.length === 0 || pointsBefore.length === 0) return ''
  const forward = pointsAfter.map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(1)},${point.y.toFixed(1)}`)
  const backward = [...pointsBefore].reverse().map(point => `L${point.x.toFixed(1)},${point.y.toFixed(1)}`)
  return `${forward.join(' ')} ${backward.join(' ')} Z`
}

/** The runs of consecutive window indexes where `values[index] < line`. */
export function runsBelow(values: readonly number[], line: number, window: IndexWindow): IndexWindow[] {
  const runs: IndexWindow[] = []
  let runStart: number | null = null
  for (let index = window.first; index <= window.last + 1; index += 1) {
    const isBelow = index <= window.last && (values[index] ?? Infinity) < line
    if (isBelow && runStart === null) runStart = index
    if (!isBelow && runStart !== null) {
      runs.push({ first: runStart, last: index - 1 })
      runStart = null
    }
  }
  return runs
}

/** Labels laid out left to right on rows: each goes on the first row where it does not overlap the one before it. */
export function stackLabels(labels: readonly { x: number; width: number }[], gap = 6): number[] {
  const rowEnds: number[] = []
  const order = labels.map((label, index) => ({ ...label, index })).sort((first, second) => first.x - second.x)
  const rows = new Array<number>(labels.length).fill(0)
  for (const label of order) {
    const start = label.x - label.width / 2
    let row = rowEnds.findIndex(rowEnd => start >= rowEnd + gap)
    if (row < 0) {
      row = rowEnds.length
      rowEnds.push(-Infinity)
    }
    rowEnds[row] = label.x + label.width / 2
    rows[label.index] = row
  }
  return rows
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** The 1sts of the months in the window (a tick each), labelled "Nov", or "Jan '27" when the year turns. */
export function monthTicks(dates: readonly string[], window: IndexWindow): { index: number; label: string }[] {
  const ticks: { index: number; label: string }[] = []
  for (let index = window.first; index <= window.last; index += 1) {
    const date = dates[index]!
    if (!date.endsWith('-01') && index !== window.first) continue
    if (index === window.first && !date.endsWith('-01')) continue
    const [year, month] = date.split('-')
    const monthName = MONTH_NAMES[Number(month) - 1] ?? ''
    ticks.push({ index, label: month === '01' ? `${monthName} '${year!.slice(2)}` : monthName })
  }
  return ticks
}


/** The chart opens on "Until last deal ends" when the refi at the lowest ARV brings nothing back (or costs money):
 * the question then is whether the money holds until every deal is out. Otherwise on the deal's own lifecycle. */
export function defaultDealImpactRange(cashOutWireAtLowestArvDollars: number | null | undefined): DealImpactRange {
  return cashOutWireAtLowestArvDollars != null && cashOutWireAtLowestArvDollars <= 0 ? 'until_last_deal_ends' : 'deal_lifecycle'
}

/** The last day of the deals in the timeline and the incoming one: each one's refi, or today for a refi already late. */
export function lastDealEndDate(refiDates: readonly (string | null | undefined)[], todayIsoDate: string): string | null {
  const ends = refiDates.filter((date): date is string => !!date).map(date => (date < todayIsoDate ? todayIsoDate : date)).sort()
  return ends.length ? ends[ends.length - 1]! : null
}
