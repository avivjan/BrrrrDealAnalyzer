<script setup lang="ts">
/**
 * The deal impact chart (tasks/todo/DealImpactSimulator.md, A): the timeline as it is ("before", a thin muted line)
 * and with the deal or its changes ("after", in the deal's colour), the gap between them shaded, the days under the
 * reserve and under zero tinted, and the places to look called out: the deal's key dates as flags, the new low
 * point, and the day it is back above the reserve. Fitted to its width (no scrolling); the range chips choose the
 * window, "Deal lifecycle" by default.
 *
 * Hover (mouse or pen) or tap shows a tooltip: the date, both balances, the difference and the deal's rows that day.
 * The arrow keys step through days. Colours are Tailwind tokens (every look, light and dark) and the deal's colour.
 */
import { computed, onMounted, onUnmounted, ref, useId } from 'vue'

import type { DealKeyDate } from '../../../types/liquidity'
import type { DatedAmount } from '../../../utils/dealCashRowsPreview'
import { formatMoney, formatSignedMoney } from '../../../utils/money'
import { formatDollarsCompact, linePath, niceGridSteps, type Point } from '../chart/geometry'
import {
  DEAL_IMPACT_RANGES,
  gapPolygonPath,
  monthTicks,
  runsBelow,
  stackLabels,
  valueRangeFor,
  windowForRange,
  windowIndexForX,
  xForWindowIndex,
  yForValue,
  type DealImpactRange,
  type PlotBox,
} from './dealImpactGeometry'

export interface DealRowOnADay {
  description: string
  amountDollars: number
}

const props = defineProps<{
  dates: string[]
  balancesBefore: number[]
  balancesAfter: number[]
  reserveDollars: number
  todayIsoDate: string
  dealColorHex: string
  beforeLabel: string
  afterLabel: string
  lowestAfter: DatedAmount | null
  backAboveReserveDate: string | null
  refiDate: string | null
  keyDates: DealKeyDate[]
  dealRowsByDate: Record<string, DealRowOnADay[]>
}>()

const KEY_DATE_SHORT_LABELS: Record<string, string> = {
  contract_signed: 'Contract',
  purchase_closed: 'Closing',
  rehab_completed: 'Rehab done',
  tenant_moved_in: 'Tenant in',
  property_tax_bill_paid_on_november_30: 'Nov 30 tax',
  refi_closed: 'Refi',
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(isoDate: string): string {
  const [, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}`
}
function longDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}, ${year}`
}

// --- size ----------------------------------------------------------------------------------------------------
const plotContainerRef = ref<HTMLDivElement | null>(null)
const width = ref(0)
const height = ref(0)
let resizeObserver: ResizeObserver | null = null
function measure() {
  if (!plotContainerRef.value) return
  width.value = plotContainerRef.value.clientWidth
  height.value = plotContainerRef.value.clientHeight
}
onMounted(() => {
  measure()
  if (typeof ResizeObserver !== 'undefined' && plotContainerRef.value) {
    resizeObserver = new ResizeObserver(measure)
    resizeObserver.observe(plotContainerRef.value)
  }
})
onUnmounted(() => resizeObserver?.disconnect())

// --- window and scales ---------------------------------------------------------------------------------------
const range = ref<DealImpactRange>('deal_lifecycle')
const window_ = computed(() => windowForRange(props.dates, range.value, props.todayIsoDate,
  { refiDate: props.refiDate, lowestDate: props.lowestAfter?.date ?? null }))
const indexOfDate = (isoDate: string) => props.dates.indexOf(isoDate)
const isInWindow = (index: number) => index >= window_.value.first && index <= window_.value.last

const FLAG_ROW_HEIGHT = 16
const PAD_LEFT = 60
const PAD_RIGHT = 14
const PAD_BOTTOM = 26

/** The key dates inside the window, laid out on label rows above the plot. */
const flags = computed(() => {
  const roughBox: PlotBox = { left: PAD_LEFT, right: Math.max(PAD_LEFT + 1, width.value - PAD_RIGHT), top: 0, bottom: 0 }
  const inWindow = props.keyDates
    .map(keyDate => ({ keyDate, index: indexOfDate(keyDate.date) }))
    .filter(flag => flag.index >= 0 && isInWindow(flag.index))
    .map(flag => {
      const label = KEY_DATE_SHORT_LABELS[flag.keyDate.key] ?? flag.keyDate.description
      return { ...flag, label, x: xForWindowIndex(flag.index, window_.value, roughBox), labelWidth: label.length * 5.6 + 12 }
    })
  const rows = stackLabels(inWindow.map(flag => ({ x: flag.x, width: flag.labelWidth })))
  return inWindow.map((flag, position) => ({ ...flag, row: rows[position] ?? 0 }))
})
const flagRowCount = computed(() => flags.value.reduce((most, flag) => Math.max(most, flag.row + 1), 0))

const box = computed<PlotBox>(() => ({
  left: PAD_LEFT,
  right: Math.max(PAD_LEFT + 1, width.value - PAD_RIGHT),
  top: 14 + flagRowCount.value * FLAG_ROW_HEIGHT + 8,
  bottom: Math.max(40, height.value - PAD_BOTTOM),
}))
const valueRange = computed(() => valueRangeFor(props.balancesBefore, props.balancesAfter, window_.value, props.reserveDollars))
const x = (index: number) => xForWindowIndex(index, window_.value, box.value)
const y = (value: number) => yForValue(value, valueRange.value, box.value)
const clampedY = (value: number) => Math.min(box.value.bottom, Math.max(box.value.top, y(value)))

function pointsOf(balances: readonly number[]): Point[] {
  const points: Point[] = []
  for (let index = window_.value.first; index <= window_.value.last; index += 1) {
    const balance = balances[index]
    if (balance !== undefined) points.push({ x: x(index), y: y(balance) })
  }
  return points
}
const pointsBefore = computed(() => pointsOf(props.balancesBefore))
const pointsAfter = computed(() => pointsOf(props.balancesAfter))
const beforePath = computed(() => linePath(pointsBefore.value))
const afterPath = computed(() => linePath(pointsAfter.value))
const gapPath = computed(() => gapPolygonPath(pointsBefore.value, pointsAfter.value))

const dayWidth = computed(() => (box.value.right - box.value.left) / Math.max(1, window_.value.last - window_.value.first))
const bandOf = (run: { first: number; last: number }) => ({
  x: Math.max(box.value.left, x(run.first) - dayWidth.value / 2),
  width: Math.max(1, x(run.last) - x(run.first) + dayWidth.value),
})
const belowReserveBands = computed(() => runsBelow(props.balancesAfter, props.reserveDollars, window_.value).map(bandOf))
const belowZeroBands = computed(() => runsBelow(props.balancesAfter, 0, window_.value).map(bandOf))

const gridSteps = computed(() => niceGridSteps(valueRange.value.min, valueRange.value.max, 5)
  .map(value => ({ value, y: y(value) }))
  .filter(step => step.y >= box.value.top - 2 && step.y <= box.value.bottom + 2))
/** Month ticks; a label too close to the one before it is dropped (a narrow phone, a long range). */
const ticks = computed(() => {
  const minimumLabelSpacing = 42
  let lastLabelX = -Infinity
  return monthTicks(props.dates, window_.value).map(tick => {
    const tickX = x(tick.index)
    const showsItsLabel = tickX - lastLabelX >= minimumLabelSpacing
    if (showsItsLabel) lastLabelX = tickX
    return { ...tick, x: tickX, showsItsLabel }
  })
})

const todayIndex = computed(() => indexOfDate(props.todayIsoDate))
const lowestPin = computed(() => {
  if (!props.lowestAfter) return null
  const index = indexOfDate(props.lowestAfter.date)
  if (index < 0 || !isInWindow(index)) return null
  const pinY = y(props.lowestAfter.amountDollars)
  const label = `Lowest ${formatMoney(Math.round(props.lowestAfter.amountDollars))} · ${shortDate(props.lowestAfter.date)}`
  const labelWidth = label.length * 6 + 16
  const labelX = Math.min(Math.max(x(index) - labelWidth / 2, box.value.left), box.value.right - labelWidth)
  const labelAbove = pinY - box.value.top > 34
  return { x: x(index), y: pinY, label, labelWidth, labelX, labelY: labelAbove ? pinY - 30 : pinY + 12 }
})
const recoveryPin = computed(() => {
  if (!props.backAboveReserveDate) return null
  const index = indexOfDate(props.backAboveReserveDate)
  if (index < 0 || !isInWindow(index)) return null
  const label = `Back above reserve · ${shortDate(props.backAboveReserveDate)}`
  const labelWidth = label.length * 6 + 16
  const pinY = y(props.balancesAfter[index] ?? 0)
  return { x: x(index), y: pinY, label, labelWidth, labelX: Math.min(x(index) + 8, box.value.right - labelWidth), labelY: pinY + 10 }
})

// --- interaction ---------------------------------------------------------------------------------------------
const hoveredIndex = ref<number | null>(null)
const pinnedIndex = ref<number | null>(null)
const activeIndex = computed(() => hoveredIndex.value ?? pinnedIndex.value)

function indexAtClientX(clientX: number): number {
  const rect = plotContainerRef.value?.getBoundingClientRect()
  return windowIndexForX(clientX - (rect?.left ?? 0), window_.value, box.value)
}
function onPointerMove(event: PointerEvent) {
  if (event.pointerType === 'touch') return
  hoveredIndex.value = indexAtClientX(event.clientX)
}
function onPointerDown(event: PointerEvent) {
  if (event.pointerType !== 'touch') return
  const index = indexAtClientX(event.clientX)
  pinnedIndex.value = pinnedIndex.value === index ? null : index
}
function onPointerLeave() {
  hoveredIndex.value = null
}
function onKeyDown(event: KeyboardEvent) {
  if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
  event.preventDefault()
  const current = pinnedIndex.value ?? (isInWindow(todayIndex.value) ? todayIndex.value : window_.value.first)
  const next = current + (event.key === 'ArrowRight' ? 1 : -1)
  pinnedIndex.value = Math.min(window_.value.last, Math.max(window_.value.first, next))
}
function selectRange(nextRange: DealImpactRange) {
  range.value = nextRange
  hoveredIndex.value = null
  pinnedIndex.value = null
}

const tooltip = computed(() => {
  const index = activeIndex.value
  if (index === null || !isInWindow(index)) return null
  const date = props.dates[index]!
  const before = props.balancesBefore[index] ?? 0
  const after = props.balancesAfter[index] ?? 0
  const tooltipWidth = 240
  const crosshairX = x(index)
  const left = crosshairX + 14 + tooltipWidth <= width.value ? crosshairX + 14 : Math.max(4, crosshairX - 14 - tooltipWidth)
  return { index, date, before, after, delta: after - before, rows: props.dealRowsByDate[date] ?? [], crosshairX, left, width: tooltipWidth }
})

const gradientId = useId()
</script>

<template>
  <div data-testid="deal-impact.chart" class="flex h-full min-h-0 flex-col">
    <!-- Legend and range chips -->
    <div class="flex flex-wrap items-center justify-between gap-2 px-1 pb-2">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-fg-muted">
        <span class="inline-flex items-center gap-1.5"><span class="h-0.5 w-5 rounded bg-fg-muted/70" aria-hidden="true"></span>{{ beforeLabel }}</span>
        <span class="inline-flex items-center gap-1.5 font-semibold text-fg"><span class="h-1 w-5 rounded" :style="{ backgroundColor: dealColorHex }" aria-hidden="true"></span>{{ afterLabel }}</span>
        <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-4 rounded-sm opacity-30" :style="{ backgroundColor: dealColorHex }" aria-hidden="true"></span>The difference</span>
        <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-4 rounded-sm bg-warning/20" aria-hidden="true"></span>Under the reserve</span>
        <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-4 rounded-sm bg-negative/20" aria-hidden="true"></span>Below zero</span>
      </div>
      <div role="group" aria-label="Chart range" class="flex rounded-full border-ui border-line bg-surface p-0.5">
        <button
          v-for="option in DEAL_IMPACT_RANGES"
          :key="option.key"
          type="button"
          :data-testid="`deal-impact.range.${option.key}`"
          class="rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors duration-fast ease-standard"
          :class="range === option.key ? 'bg-primary text-primary-fg' : 'text-fg-muted hover:text-fg'"
          :aria-pressed="range === option.key"
          @click="selectRange(option.key)"
        >{{ option.label }}</button>
      </div>
    </div>

    <div
      ref="plotContainerRef"
      data-testid="deal-impact.plot"
      class="relative min-h-0 flex-1 select-none rounded-card bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      tabindex="0"
      :aria-label="`${beforeLabel} vs ${afterLabel}. Arrow keys step through days.`"
      @keydown="onKeyDown"
    >
      <svg
        v-if="width > 0 && height > 0 && window_.last >= window_.first"
        :width="width"
        :height="height"
        :viewBox="`0 0 ${width} ${height}`"
        class="absolute inset-0 touch-pan-y"
        role="img"
        :aria-label="`Balance ${beforeLabel.toLowerCase()} and ${afterLabel.toLowerCase()}`"
        style="font-family: var(--font-mono)"
        @pointermove="onPointerMove"
        @pointerdown="onPointerDown"
        @pointerleave="onPointerLeave"
      >
        <defs>
          <linearGradient :id="`${gradientId}-gap`" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" :stop-color="dealColorHex" stop-opacity="0.28" />
            <stop offset="1" :stop-color="dealColorHex" stop-opacity="0.12" />
          </linearGradient>
        </defs>

        <!-- Under the reserve / below zero, on the projected line -->
        <!-- Only under the line it crosses: below the reserve (warning), below zero (negative) -->
        <rect v-for="(band, position) in belowReserveBands" :key="`reserve-${position}`" data-part="below-reserve-zone"
          :x="band.x" :y="clampedY(reserveDollars)" :width="band.width" :height="Math.max(0, box.bottom - clampedY(reserveDollars))" class="fill-warning" fill-opacity="0.12" />
        <rect v-for="(band, position) in belowZeroBands" :key="`zero-${position}`" data-part="below-zero-zone"
          :x="band.x" :y="clampedY(0)" :width="band.width" :height="Math.max(0, box.bottom - clampedY(0))" class="fill-negative" fill-opacity="0.16" />

        <!-- Grid and y labels -->
        <g>
          <template v-for="step in gridSteps" :key="step.value">
            <line :x1="box.left" :x2="box.right" :y1="step.y" :y2="step.y" class="stroke-line" stroke-width="1" />
            <text :x="box.left - 8" :y="step.y" text-anchor="end" dominant-baseline="middle" font-size="10" class="fill-fg-muted">{{ formatDollarsCompact(step.value) }}</text>
          </template>
        </g>

        <!-- Month ticks -->
        <g>
          <template v-for="tick in ticks" :key="tick.index">
            <line :x1="tick.x" :x2="tick.x" :y1="box.top" :y2="box.bottom" class="stroke-line" stroke-width="1" stroke-dasharray="2 4" />
            <text v-if="tick.showsItsLabel" :x="tick.x + 4" :y="box.bottom + 16" font-size="10" font-weight="600" class="fill-fg-muted">{{ tick.label }}</text>
          </template>
        </g>

        <!-- Zero and the reserve -->
        <line :x1="box.left" :x2="box.right" :y1="y(0)" :y2="y(0)" class="stroke-negative" stroke-width="1.25" stroke-opacity="0.7" />
        <text :x="box.right - 4" :y="y(0) - 4" text-anchor="end" font-size="9" font-weight="700" class="fill-negative">0</text>
        <line data-part="reserve-line" :x1="box.left" :x2="box.right" :y1="y(reserveDollars)" :y2="y(reserveDollars)" class="stroke-warning" stroke-width="1.25" stroke-dasharray="6 4" />
        <text :x="box.right - 4" :y="y(reserveDollars) - 4" text-anchor="end" font-size="9" font-weight="700" letter-spacing="0.06em" class="fill-warning">reserve</text>

        <!-- Key-date flags -->
        <g data-part="key-date-flags">
          <g v-for="flag in flags" :key="flag.keyDate.key" data-part="key-date-flag" :data-key-date="flag.keyDate.key">
            <line :x1="flag.x" :x2="flag.x" :y1="14 + flag.row * FLAG_ROW_HEIGHT + 12" :y2="box.bottom" class="stroke-fg-muted" stroke-opacity="0.35" stroke-width="1" stroke-dasharray="3 3" />
            <rect :x="flag.x - flag.labelWidth / 2" :y="2 + flag.row * FLAG_ROW_HEIGHT" :width="flag.labelWidth" height="14" rx="7" class="fill-surface-2 stroke-line" stroke-width="1" />
            <text :x="flag.x" :y="9 + flag.row * FLAG_ROW_HEIGHT" text-anchor="middle" dominant-baseline="middle" font-size="9" font-weight="700" class="fill-fg">{{ flag.label }}</text>
          </g>
        </g>

        <!-- Today -->
        <g v-if="isInWindow(todayIndex)" data-part="today">
          <line :x1="x(todayIndex)" :x2="x(todayIndex)" :y1="box.top" :y2="box.bottom" class="stroke-primary" stroke-width="6" stroke-opacity="0.12" />
          <line :x1="x(todayIndex)" :x2="x(todayIndex)" :y1="box.top" :y2="box.bottom" class="stroke-primary" stroke-width="1.25" stroke-dasharray="3 3" />
        </g>

        <!-- The difference, then the two lines -->
        <path data-part="gap" :d="gapPath" :fill="`url(#${gradientId}-gap)`" stroke="none" />
        <path data-part="before-line" :d="beforePath" fill="none" class="stroke-fg-muted" stroke-opacity="0.8" stroke-width="1.5" stroke-linejoin="round" />
        <path data-part="after-line" :d="afterPath" fill="none" :stroke="dealColorHex" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />

        <!-- The new low point -->
        <g v-if="lowestPin" data-part="lowest-pin">
          <circle :cx="lowestPin.x" :cy="lowestPin.y" r="5" :fill="dealColorHex" class="stroke-surface" stroke-width="2" />
          <rect :x="lowestPin.labelX" :y="lowestPin.labelY" :width="lowestPin.labelWidth" height="20" rx="10" class="fill-fg" />
          <text :x="lowestPin.labelX + lowestPin.labelWidth / 2" :y="lowestPin.labelY + 10" text-anchor="middle" dominant-baseline="middle" font-size="10" font-weight="700" class="fill-surface">{{ lowestPin.label }}</text>
        </g>

        <!-- Back above the reserve -->
        <g v-if="recoveryPin" data-part="recovery-pin">
          <circle :cx="recoveryPin.x" :cy="recoveryPin.y" r="4.5" class="fill-positive stroke-surface" stroke-width="2" />
          <rect :x="recoveryPin.labelX" :y="recoveryPin.labelY" :width="recoveryPin.labelWidth" height="18" rx="9" class="fill-positive" fill-opacity="0.15" />
          <text :x="recoveryPin.labelX + recoveryPin.labelWidth / 2" :y="recoveryPin.labelY + 9" text-anchor="middle" dominant-baseline="middle" font-size="10" font-weight="700" class="fill-positive">{{ recoveryPin.label }}</text>
        </g>

        <!-- Crosshair -->
        <g v-if="tooltip" data-part="crosshair">
          <line :x1="tooltip.crosshairX" :x2="tooltip.crosshairX" :y1="box.top" :y2="box.bottom" class="stroke-fg" stroke-opacity="0.4" stroke-width="1" />
          <circle :cx="tooltip.crosshairX" :cy="y(tooltip.before)" r="3.5" class="fill-fg-muted stroke-surface" stroke-width="1.5" />
          <circle :cx="tooltip.crosshairX" :cy="y(tooltip.after)" r="4.5" :fill="dealColorHex" class="stroke-surface" stroke-width="2" />
        </g>
      </svg>

      <!-- Tooltip: the date, both balances, the difference, the deal's rows that day -->
      <div
        v-if="tooltip"
        data-testid="deal-impact.tooltip"
        class="pointer-events-none absolute top-3 z-10 rounded-card border-ui border-line bg-surface/95 px-3.5 py-2.5 text-xs shadow-3 backdrop-blur-sm"
        :style="{ left: `${tooltip.left}px`, width: `${tooltip.width}px` }"
      >
        <div class="mb-1.5 font-semibold text-fg">{{ longDate(tooltip.date) }}</div>
        <div class="flex justify-between gap-2 text-fg-muted"><span>{{ beforeLabel }}</span><span class="numeric">{{ formatSignedMoney(Math.round(tooltip.before)) }}</span></div>
        <div class="flex justify-between gap-2 font-semibold text-fg"><span>{{ afterLabel }}</span><span class="numeric" :class="tooltip.after < 0 ? 'text-negative' : ''">{{ formatSignedMoney(Math.round(tooltip.after)) }}</span></div>
        <div data-testid="deal-impact.tooltip.delta" class="mt-0.5 flex justify-between gap-2 border-t border-line pt-0.5 text-fg-muted">
          <span>Difference</span><span class="numeric font-semibold" :class="tooltip.delta < 0 ? 'text-negative' : tooltip.delta > 0 ? 'text-positive' : ''">{{ formatSignedMoney(Math.round(tooltip.delta)) }}</span>
        </div>
        <ul v-if="tooltip.rows.length" class="mt-1.5 space-y-0.5 border-t border-line pt-1.5">
          <li v-for="(row, position) in tooltip.rows.slice(0, 5)" :key="position" class="flex justify-between gap-2">
            <span class="min-w-0 truncate text-fg">{{ row.description }}</span>
            <span class="numeric shrink-0" :class="row.amountDollars < 0 ? 'text-negative' : 'text-positive'">{{ formatSignedMoney(row.amountDollars) }}</span>
          </li>
          <li v-if="tooltip.rows.length > 5" class="text-[10px] text-fg-muted">+{{ tooltip.rows.length - 5 }} more</li>
        </ul>
      </div>
    </div>
  </div>
</template>
