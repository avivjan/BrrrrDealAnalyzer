<script setup lang="ts">
/**
 * The liquidity timeline, drawn in SVG.
 *
 * UI v2 rewrite of the v1 `<canvas>` chart. The *contract* is the v1 one and
 * is pinned by `TimelineChart.test.ts` (written against the canvas version
 * first): props `days` / `globalMin` / `globalMinDates` / `firstNegativeDate`,
 * one emit `selectDay(date)`, `defineExpose({ centerOnToday })`, a focusable
 * `chart.container` that handles the arrow keys itself (first press lands on
 * day 0, then steps and clamps, emitting every time; Enter re-emits), hover
 * winning over selection for the tooltip, a click under 4 px of travel
 * selecting a day while a longer drag pans, and wheel panning.
 *
 * What changed: the plot is a virtualised SVG (only the visible window of days
 * is in the DOM), so it is crisp at any DPR, restyles itself on a look or mode
 * switch, and can be animated by CSS or GSAP later. Colours still come from
 * the 32 `--chart-*` tokens through `chartToken()`, read once into a computed
 * that re-evaluates when `themeEpoch` changes — `chartTokens.test.ts` checks
 * that each of the 32 names is read exactly once in this file.
 *
 * Geometry is pure (`./chart/geometry.ts`). No size, padding or transform
 * transition may be applied to this element or any ancestor: the plot is
 * re-measured from a ResizeObserver.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { chartToken } from '../../design/chartTokens'
import { themeEpoch } from '../../design/theme'
import type { DayBucket } from '../../types/liquidity'
import { todayISO } from '../../utils/liquidityEngine'
import {
  DAY_WIDTH,
  MONTH_NAMES,
  PAD_BOTTOM,
  PAD_LEFT,
  PAD_TOP,
  WEEKDAY_NAMES,
  balanceRange,
  clampScroll,
  formatDateLong,
  formatK,
  indexForOffsetX,
  nextIndex,
  niceGridSteps,
  parseDateParts,
  scrollToCentre,
  scrollToReveal,
  visibleRange,
  weekday,
  xForIndex,
  yForBalance,
} from './chart/geometry'

const props = defineProps<{
  days: DayBucket[]
  globalMin: number
  globalMinDates: string[]
  firstNegativeDate: string | null
}>()

const emit = defineEmits<{
  (e: 'selectDay', date: string): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const width = ref(0)
const height = ref(0)
const scrollX = ref(0)
const hoveredIndex = ref<number | null>(null)
const selectedIndex = ref<number | null>(null)
const isDragging = ref(false)
let dragStartX = 0
let dragStartScroll = 0
let dragTravel = 0

const today = todayISO()

/**
 * The 32 chart colours, read from the active look. Reading `themeEpoch`
 * makes this recompute after `theme.ts` reset the token cache, so a look or
 * mode switch recolours the plot without a redraw call.
 */
const C = computed(() => {
  void themeEpoch.value
  return {
    bg: chartToken('bg'),
    grid: chartToken('grid'),
    axisText: chartToken('axis-text'),
    reserveBand: chartToken('reserve-band'),
    weekendBand: chartToken('weekend-band'),
    todayBand: chartToken('today-band'),
    monthLine: chartToken('month-line'),
    dayLine: chartToken('day-line'),
    monthLabel: chartToken('month-label'),
    dayToday: chartToken('day-today'),
    dayHover: chartToken('day-hover'),
    dayActive: chartToken('day-active'),
    dayIdle: chartToken('day-idle'),
    markerToday: chartToken('marker-today'),
    markerIdle: chartToken('marker-idle'),
    todayLine: chartToken('today-line'),
    netPositive: chartToken('net-positive'),
    netNegative: chartToken('net-negative'),
    inflowFillHover: chartToken('inflow-fill-hover'),
    inflowFill: chartToken('inflow-fill'),
    inflowStrokeHover: chartToken('inflow-stroke-hover'),
    inflowStroke: chartToken('inflow-stroke'),
    outflowFillHover: chartToken('outflow-fill-hover'),
    outflowFill: chartToken('outflow-fill'),
    outflowStrokeHover: chartToken('outflow-stroke-hover'),
    outflowStroke: chartToken('outflow-stroke'),
    reserveLine: chartToken('reserve-line'),
    baseline: chartToken('baseline'),
    balanceDot: chartToken('balance-dot'),
    balanceDotCore: chartToken('balance-dot-core'),
    minNegative: chartToken('min-negative'),
    minWarning: chartToken('min-warning'),
  }
})

const count = computed(() => props.days.length)
const range = computed(() => balanceRange(props.days.map((d) => d.balance_k)))
const plotBottom = computed(() => height.value - PAD_BOTTOM)
const y = (balance: number) => yForBalance(balance, height.value, range.value)
const x = (i: number) => xForIndex(i, scrollX.value)

/** Hover wins over selection for the highlight and the tooltip. */
const activeIndex = computed(() => hoveredIndex.value ?? selectedIndex.value)
const activeDay = computed<DayBucket | null>(() => {
  const idx = activeIndex.value
  if (idx === null || idx < 0 || idx >= count.value) return null
  return props.days[idx] ?? null
})

const zeroY = computed(() => y(0))
const zeroVisible = computed(() => zeroY.value >= PAD_TOP && zeroY.value <= plotBottom.value)
const baseY = computed(() => (zeroVisible.value ? zeroY.value : plotBottom.value))

const gridSteps = computed(() =>
  niceGridSteps(range.value.min, range.value.max, 6)
    .map((value) => ({ value, y: y(value) }))
    .filter((step) => step.y >= PAD_TOP - 5 && step.y <= plotBottom.value + 5),
)

const window_ = computed(() => visibleRange(scrollX.value, width.value, count.value))

interface DayShape {
  i: number
  x: number
  day: DayBucket
  weekend: boolean
  isToday: boolean
  firstOfMonth: boolean
  monthLabel: string | null
  dayNumber: number
  weekdayName: string
  hasTxns: boolean
  hovered: boolean
  barTop: number
  barHeight: number
  positive: boolean
}

/** Everything the template needs per visible day, computed once per render. */
const shapes = computed<DayShape[]>(() => {
  const [first, last] = window_.value
  const out: DayShape[] = []
  let prevMonth = first > 0 ? parseDateParts(props.days[first - 1]!.date).slice(0, 2).join('-') : ''
  for (let i = first; i <= last; i += 1) {
    const day = props.days[i]!
    const [yr, mo, dy] = parseDateParts(day.date)
    const monthKey = `${yr}-${mo}`
    const wd = weekday(day.date)
    const balY = y(day.balance_k)
    const positive = day.balance_k >= 0
    out.push({
      i,
      x: x(i),
      day,
      weekend: wd === 0 || wd === 6,
      isToday: day.date === today,
      firstOfMonth: parseInt(dy, 10) === 1,
      monthLabel: monthKey !== prevMonth ? `${MONTH_NAMES[parseInt(mo, 10) - 1] ?? ''} '${yr.slice(2)}` : null,
      dayNumber: parseInt(dy, 10),
      weekdayName: WEEKDAY_NAMES[wd] ?? '',
      hasTxns: day.net_k !== 0,
      hovered: i === activeIndex.value,
      barTop: positive ? Math.min(balY, baseY.value) : baseY.value,
      barHeight: Math.abs(baseY.value - balY),
      positive,
    })
    prevMonth = monthKey
  }
  return out
})

/** The running-balance line through the visible days (plus one each side, so it enters and leaves the frame). */
const balancePath = computed(() => {
  const [first, last] = window_.value
  if (last < first) return ''
  const from = Math.max(0, first - 1)
  const to = Math.min(count.value - 1, last + 1)
  let d = ''
  for (let i = from; i <= to; i += 1) {
    d += `${i === from ? 'M' : 'L'}${x(i).toFixed(1)},${y(props.days[i]!.balance_k).toFixed(1)} `
  }
  return d.trim()
})

const minMarkers = computed(() => {
  const [first, last] = window_.value
  return props.globalMinDates
    .map((date) => props.days.findIndex((d) => d.date === date))
    .filter((idx) => idx >= first && idx <= last)
    .map((idx) => ({ idx, x: x(idx), y: y(props.days[idx]!.balance_k), negative: props.days[idx]!.balance_k < 0 }))
})

const crosshair = computed(() => {
  const idx = activeIndex.value
  const [first, last] = window_.value
  if (idx === null || idx < first || idx > last) return null
  const day = props.days[idx]!
  return { y: y(day.balance_k), x: x(idx), label: formatK(day.balance_k), negative: day.balance_k < 0 }
})

const BAR_GAP = 2
const barWidth = DAY_WIDTH - BAR_GAP * 2

// ---------------------------------------------------------------------------
// interaction
// ---------------------------------------------------------------------------

function indexAt(clientX: number): number | null {
  const el = containerRef.value
  if (!el) return null
  const rect = el.getBoundingClientRect()
  return indexForOffsetX(clientX - rect.left, scrollX.value, count.value)
}

function centerOnToday() {
  const todayIdx = props.days.findIndex((d) => d.date === today)
  if (todayIdx < 0) return
  scrollX.value = scrollToCentre(todayIdx, width.value, count.value)
}

function onPointerDown(e: PointerEvent) {
  isDragging.value = true
  dragStartX = e.clientX
  dragStartScroll = scrollX.value
  dragTravel = 0
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  const idx = indexAt(e.clientX)
  if (!isDragging.value) {
    hoveredIndex.value = idx
    return
  }
  dragTravel = Math.max(dragTravel, Math.abs(e.clientX - dragStartX))
  scrollX.value = clampScroll(dragStartScroll - (e.clientX - dragStartX), count.value, width.value)
  hoveredIndex.value = idx
}

function onPointerUp(e: PointerEvent) {
  if (!isDragging.value) return
  isDragging.value = false
  ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  // A click, not a pan: under 4 px of travel selects the day under the pointer.
  if (dragTravel < 4) {
    const idx = indexAt(e.clientX)
    if (idx !== null) {
      selectedIndex.value = idx
      emit('selectDay', props.days[idx]!.date)
    }
  }
}

function onPointerLeave() {
  if (!isDragging.value) hoveredIndex.value = null
}

function onWheel(e: WheelEvent) {
  scrollX.value = clampScroll(scrollX.value + (e.deltaX || e.deltaY), count.value, width.value)
}

function onKeyDown(e: KeyboardEvent) {
  const current = selectedIndex.value ?? hoveredIndex.value
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault()
    const next = nextIndex(current, e.key, count.value)
    if (next === null) return
    selectedIndex.value = next
    scrollX.value = scrollToReveal(next, scrollX.value, width.value, count.value)
    emit('selectDay', props.days[next]!.date)
  } else if (e.key === 'Enter' && current !== null && props.days[current]) {
    emit('selectDay', props.days[current]!.date)
  }
}

// ---------------------------------------------------------------------------
// measurement
// ---------------------------------------------------------------------------

let resizeObs: ResizeObserver | null = null

function measure() {
  const el = containerRef.value
  if (!el) return
  width.value = el.clientWidth
  height.value = el.clientHeight
  scrollX.value = clampScroll(scrollX.value, count.value, width.value)
}

onMounted(() => {
  measure()
  centerOnToday()
  if (typeof ResizeObserver !== 'undefined') {
    resizeObs = new ResizeObserver(() => measure())
    if (containerRef.value) resizeObs.observe(containerRef.value)
  }
})

onUnmounted(() => {
  resizeObs?.disconnect()
})

watch(
  () => props.days,
  () => {
    scrollX.value = clampScroll(scrollX.value, count.value, width.value)
    if (selectedIndex.value !== null && selectedIndex.value >= count.value) selectedIndex.value = null
    if (hoveredIndex.value !== null && hoveredIndex.value >= count.value) hoveredIndex.value = null
  },
)

defineExpose({ centerOnToday })
</script>

<template>
  <!--
    The focus ring is drawn inside the box: the plot is edge to edge. No size,
    padding or transform transition here — the plot is re-measured on resize.
  -->
  <div
    ref="containerRef"
    data-testid="chart.container"
    class="relative h-full w-full select-none overflow-hidden bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
    tabindex="0"
    @keydown="onKeyDown"
  >
    <svg
      data-testid="chart.svg"
      role="img"
      :aria-label="`Running balance, ${count} days`"
      :width="width"
      :height="height"
      :viewBox="`0 0 ${width} ${height}`"
      class="absolute inset-0 cursor-crosshair touch-none"
      :style="{ fontFamily: 'var(--font-mono)' }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="onPointerLeave"
      @wheel.prevent="onWheel"
    >
      <rect data-part="bg" x="0" y="0" :width="width" :height="height" :fill="C.bg" />

      <template v-if="count > 0 && width > 0">
        <!-- Negative region wash, behind everything -->
        <rect
          v-if="range.min < 0 && zeroVisible"
          data-part="negative-band"
          :x="PAD_LEFT"
          :y="Math.max(zeroY, PAD_TOP)"
          :width="Math.max(0, width - PAD_LEFT)"
          :height="Math.max(0, Math.min(y(range.min), plotBottom) - Math.max(zeroY, PAD_TOP))"
          :fill="C.reserveBand"
        />

        <!-- Horizontal grid + y labels -->
        <g data-part="grid">
          <template v-for="step in gridSteps" :key="step.value">
            <line :x1="PAD_LEFT" :x2="width" :y1="step.y" :y2="step.y" :stroke="C.grid" stroke-width="1" />
            <text :x="PAD_LEFT - 8" :y="step.y" text-anchor="end" dominant-baseline="middle" font-size="11" :fill="C.axisText">
              {{ formatK(step.value) }}
            </text>
          </template>
        </g>

        <!-- Days: bands, rules, labels -->
        <g data-part="days">
          <g v-for="s in shapes" :key="s.day.date" :data-date="s.day.date" :aria-label="`${s.day.date} balance ${formatK(s.day.balance_k)}`">
            <rect v-if="s.weekend" :x="s.x - DAY_WIDTH / 2" :y="PAD_TOP" :width="DAY_WIDTH" :height="plotBottom - PAD_TOP" :fill="C.weekendBand" />
            <rect v-if="s.hovered" :x="s.x - DAY_WIDTH / 2" :y="PAD_TOP" :width="DAY_WIDTH" :height="plotBottom - PAD_TOP" :fill="C.todayBand" />
            <line
              :x1="s.x - DAY_WIDTH / 2"
              :x2="s.x - DAY_WIDTH / 2"
              :y1="PAD_TOP"
              :y2="plotBottom"
              :stroke="s.firstOfMonth ? C.monthLine : C.dayLine"
              :stroke-width="s.firstOfMonth ? 1 : 0.5"
            />
            <text v-if="s.monthLabel" :x="s.x + 30" :y="plotBottom + 34" text-anchor="middle" font-size="10" font-weight="700" :fill="C.monthLabel">
              {{ s.monthLabel }}
            </text>
            <text
              :x="s.x"
              :y="plotBottom + 14"
              text-anchor="middle"
              font-size="10"
              :font-weight="s.isToday || s.hovered ? 700 : 400"
              :fill="s.isToday ? C.dayToday : s.hovered ? C.dayHover : s.hasTxns ? C.dayActive : C.dayIdle"
            >
              {{ s.dayNumber }}
            </text>
            <text :x="s.x" :y="plotBottom + 24" text-anchor="middle" font-size="8" :fill="s.isToday ? C.markerToday : C.markerIdle">
              {{ s.weekdayName }}
            </text>
            <line
              v-if="s.isToday"
              :x1="s.x"
              :x2="s.x"
              :y1="PAD_TOP"
              :y2="plotBottom"
              :stroke="C.todayLine"
              stroke-width="1.5"
              stroke-dasharray="3 3"
            />
            <circle v-if="s.hasTxns" :cx="s.x" :cy="plotBottom + 3" r="1.5" :fill="s.day.net_k > 0 ? C.netPositive : C.netNegative" />
            <!-- Balance bar -->
            <rect
              data-part="bar"
              :x="s.x - barWidth / 2"
              :y="s.barTop"
              :width="barWidth"
              :height="Math.max(0, s.barHeight)"
              rx="2"
              :fill="s.positive ? (s.hovered ? C.inflowFillHover : C.inflowFill) : s.hovered ? C.outflowFillHover : C.outflowFill"
              :stroke="s.positive ? (s.hovered ? C.inflowStrokeHover : C.inflowStroke) : s.hovered ? C.outflowStrokeHover : C.outflowStroke"
              :stroke-width="s.hovered ? 1.5 : 0.5"
            />
          </g>
        </g>

        <!-- Zero line, on top of the bars -->
        <line v-if="zeroVisible" data-part="zero-line" :x1="PAD_LEFT" :x2="width" :y1="zeroY" :y2="zeroY" :stroke="C.reserveLine" stroke-width="2" />

        <!-- Running balance line -->
        <path v-draw-on data-part="balance-line" :d="balancePath" fill="none" :stroke="C.balanceDot" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />

        <!-- Crosshair + y badge for the active day -->
        <g v-if="crosshair" data-part="crosshair">
          <line :x1="PAD_LEFT" :x2="width" :y1="crosshair.y" :y2="crosshair.y" :stroke="C.baseline" stroke-width="1" stroke-dasharray="2 2" />
          <circle :cx="crosshair.x" :cy="crosshair.y" r="4.5" :fill="C.balanceDot" :stroke="C.balanceDotCore" stroke-width="2" />
          <rect x="0" :y="crosshair.y - 10" :width="PAD_LEFT - 4" height="20" rx="3" :fill="C.balanceDot" />
          <text :x="PAD_LEFT - 8" :y="crosshair.y" text-anchor="end" dominant-baseline="middle" font-size="10" font-weight="700" :fill="C.balanceDotCore">
            {{ crosshair.label }}
          </text>
        </g>

        <!-- Global-minimum markers -->
        <g data-part="min-markers">
          <path
            v-for="m in minMarkers"
            :key="m.idx"
            :d="`M${m.x},${m.y - 8} L${m.x - 5},${m.y - 14} L${m.x + 5},${m.y - 14} Z`"
            :fill="m.negative ? C.minNegative : C.minWarning"
          />
        </g>
      </template>
    </svg>

    <!-- Hover tooltip: day, balance, transactions -->
    <Transition name="fade">
      <div
        v-if="activeDay"
        data-testid="chart.tooltip"
        class="pointer-events-none absolute right-2 top-2 z-10 min-w-[200px] max-w-[280px] rounded-card border-ui border-line bg-surface/95 px-4 py-3 shadow-2"
      >
        <div class="mb-1.5 text-xs tracking-wide text-fg-muted">{{ formatDateLong(activeDay.date) }}</div>
        <div class="mb-1 font-display text-xl font-bold tracking-display numeric" :class="activeDay.balance_k < 0 ? 'text-negative' : 'text-primary'">
          {{ formatK(activeDay.balance_k) }}
          <span class="ml-1 font-sans text-[10px] font-normal tracking-normal text-fg-muted">EOD balance</span>
        </div>
        <div v-if="activeDay.net_k !== 0" class="mb-2 flex items-center gap-1.5 text-xs">
          <span class="text-fg-muted">Day net:</span>
          <span class="numeric font-bold" :class="activeDay.net_k > 0 ? 'text-positive' : 'text-negative'">
            {{ activeDay.net_k > 0 ? '+' : '' }}{{ activeDay.net_k.toFixed(2) }}k
          </span>
        </div>
        <div v-if="activeDay.transactions.length" class="mt-1 border-t border-line pt-2">
          <div class="mb-1.5 text-[10px] uppercase tracking-wider text-fg-muted">Transactions ({{ activeDay.transactions.length }})</div>
          <div class="space-y-1">
            <div
              v-for="txn in activeDay.transactions.slice(0, 6)"
              :key="txn.id"
              :data-testid="`chart.txn.${txn.id}`"
              class="flex items-baseline justify-between gap-3"
            >
              <span class="flex min-w-0 items-center gap-1 text-[11px] text-fg">
                <i v-if="txn.recurring_rule_id" class="pi pi-refresh shrink-0 text-[8px] text-primary" title="From a recurring rule"></i>
                <span class="truncate">{{ txn.description }}</span>
              </span>
              <span class="numeric shrink-0 text-[11px] font-bold" :class="txn.amount_k > 0 ? 'text-positive' : 'text-negative'">
                {{ txn.amount_k > 0 ? '+' : '' }}{{ txn.amount_k.toFixed(1) }}k
              </span>
            </div>
          </div>
          <div v-if="activeDay.transactions.length > 6" class="mt-1 text-[10px] text-fg-muted">+{{ activeDay.transactions.length - 6 }} more</div>
        </div>
        <div v-else class="mt-1 text-[10px] italic text-fg-muted">No transactions</div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--dur-fast) var(--ease-standard);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
