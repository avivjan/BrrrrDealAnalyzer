<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import type { DayBucket } from '../../types/liquidity'
import { todayISO } from '../../utils/liquidityEngine'

const props = defineProps<{
  days: DayBucket[]
  globalMin: number
  globalMinDates: string[]
  firstNegativeDate: string | null
}>()

const emit = defineEmits<{
  (e: 'selectDay', date: string): void
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)

const DAY_WIDTH = 48
const CHART_PADDING_TOP = 40
const CHART_PADDING_BOTTOM = 52
const CHART_PADDING_LEFT = 72
const CHART_PADDING_RIGHT = 24

const hoveredIndex = ref<number | null>(null)
const selectedIndex = ref<number | null>(null)
const scrollX = ref(0)
const isDragging = ref(false)
let dragStartX = 0
let dragStartScroll = 0
let velocityX = 0
let lastDragX = 0
let lastDragTime = 0
let animFrame = 0

const today = todayISO()
const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const WEEKDAY_NAMES = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']

const totalWidth = computed(() => props.days.length * DAY_WIDTH + CHART_PADDING_LEFT + CHART_PADDING_RIGHT)

const activeDay = computed<DayBucket | null>(() => {
  const idx = hoveredIndex.value ?? selectedIndex.value
  if (idx === null || idx < 0 || idx >= props.days.length) return null
  return props.days[idx] ?? null
})

const balanceRange = computed(() => {
  if (props.days.length === 0) return { min: 0, max: 100 }
  let min = Infinity, max = -Infinity
  for (const d of props.days) {
    if (d.balance_k < min) min = d.balance_k
    if (d.balance_k > max) max = d.balance_k
  }
  const pad = Math.max((max - min) * 0.12, 5)
  return { min: Math.min(min - pad, 0), max: max + pad }
})

function yForBalance(b: number, h: number): number {
  const { min, max } = balanceRange.value
  const range = max - min || 1
  const plotH = h - CHART_PADDING_TOP - CHART_PADDING_BOTTOM
  return CHART_PADDING_TOP + plotH * (1 - (b - min) / range)
}

function xForIndex(i: number): number {
  return CHART_PADDING_LEFT + i * DAY_WIDTH + DAY_WIDTH / 2 - scrollX.value
}

function indexForClientX(clientX: number): number | null {
  if (!containerRef.value) return null
  const rect = containerRef.value.getBoundingClientRect()
  const x = clientX - rect.left + scrollX.value - CHART_PADDING_LEFT
  const idx = Math.floor(x / DAY_WIDTH)
  if (idx < 0 || idx >= props.days.length) return null
  return idx
}

function parseDateParts(iso: string): [string, string, string] {
  const parts = iso.split('-')
  return [parts[0] ?? '', parts[1] ?? '', parts[2] ?? '']
}

function weekday(iso: string): number {
  return new Date(iso + 'T00:00:00').getDay()
}

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const container = containerRef.value
  if (!container) return

  const dpr = window.devicePixelRatio || 1
  const w = container.clientWidth
  const h = container.clientHeight
  canvas.width = w * dpr
  canvas.height = h * dpr
  canvas.style.width = w + 'px'
  canvas.style.height = h + 'px'

  const ctx = canvas.getContext('2d')!
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

  ctx.fillStyle = '#0f1117'
  ctx.fillRect(0, 0, w, h)

  const days = props.days
  if (days.length === 0) return

  const { min, max } = balanceRange.value
  const plotH = h - CHART_PADDING_TOP - CHART_PADDING_BOTTOM

  // Horizontal grid lines + Y labels
  const gridSteps = niceGridSteps(min, max, 6)
  ctx.strokeStyle = '#1e2030'
  ctx.lineWidth = 1
  ctx.font = '11px "JetBrains Mono", "SF Mono", "Fira Code", monospace'
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'

  for (const val of gridSteps) {
    const y = yForBalance(val, h)
    if (y < CHART_PADDING_TOP - 5 || y > h - CHART_PADDING_BOTTOM + 5) continue
    ctx.beginPath()
    ctx.moveTo(CHART_PADDING_LEFT, y)
    ctx.lineTo(w, y)
    ctx.stroke()
    ctx.fillStyle = '#5c6078'
    ctx.fillText(formatK(val), CHART_PADDING_LEFT - 8, y)
  }

  // Zero line — solid red, always visible
  const zeroY = yForBalance(0, h)
  const zeroVisible = zeroY >= CHART_PADDING_TOP && zeroY <= h - CHART_PADDING_BOTTOM

  // Negative region fill (drawn before bars so it sits behind)
  if (min < 0 && zeroVisible) {
    const negBottom = Math.min(yForBalance(min, h), h - CHART_PADDING_BOTTOM)
    const negTop = Math.max(zeroY, CHART_PADDING_TOP)
    ctx.fillStyle = 'rgba(239, 68, 68, 0.04)'
    ctx.fillRect(CHART_PADDING_LEFT, negTop, w - CHART_PADDING_LEFT, negBottom - negTop)
  }

  // Visible range
  const firstVisible = Math.max(0, Math.floor((scrollX.value - CHART_PADDING_LEFT) / DAY_WIDTH))
  const lastVisible = Math.min(days.length - 1, firstVisible + Math.ceil(w / DAY_WIDTH) + 2)
  const hIdx = hoveredIndex.value ?? selectedIndex.value

  // --- Day columns: vertical grid lines + labels for EVERY day ---
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'

  let prevMonth = ''
  for (let i = firstVisible; i <= lastVisible; i++) {
    const x = xForIndex(i)
    if (x < CHART_PADDING_LEFT - DAY_WIDTH || x > w + DAY_WIDTH) continue
    const d = days[i]!
    const [yr, mo, dy] = parseDateParts(d.date)
    const dayNum = parseInt(dy)
    const monthKey = yr + '-' + mo
    const wd = weekday(d.date)
    const isWeekend = wd === 0 || wd === 6
    const isHovered = i === hIdx
    const isToday = d.date === today
    const isFirstOfMonth = dayNum === 1
    const hasTxns = d.net_k !== 0

    // Weekend shading
    if (isWeekend) {
      ctx.fillStyle = 'rgba(255,255,255,0.015)'
      ctx.fillRect(x - DAY_WIDTH / 2, CHART_PADDING_TOP, DAY_WIDTH, plotH)
    }

    // Hovered column highlight
    if (isHovered) {
      ctx.fillStyle = 'rgba(99, 102, 241, 0.08)'
      ctx.fillRect(x - DAY_WIDTH / 2, CHART_PADDING_TOP, DAY_WIDTH, plotH)
    }

    // Vertical grid line per day
    ctx.strokeStyle = isFirstOfMonth ? '#2a2f45' : '#16192a'
    ctx.lineWidth = isFirstOfMonth ? 1 : 0.5
    ctx.beginPath()
    ctx.moveTo(x - DAY_WIDTH / 2, CHART_PADDING_TOP)
    ctx.lineTo(x - DAY_WIDTH / 2, h - CHART_PADDING_BOTTOM)
    ctx.stroke()

    // Month label row (drawn once per new month)
    if (monthKey !== prevMonth) {
      const mIdx = parseInt(mo) - 1
      ctx.fillStyle = '#7c82a0'
      ctx.font = 'bold 10px "JetBrains Mono", monospace'
      ctx.fillText((MONTH_NAMES[mIdx] ?? '') + ' \'' + yr.slice(2), x + 30, h - CHART_PADDING_BOTTOM + 28)
      prevMonth = monthKey
    }

    // Day number label for every day
    ctx.fillStyle = isToday ? '#818cf8' : isHovered ? '#c7d2fe' : hasTxns ? '#94a3b8' : '#3e4460'
    ctx.font = (isToday || isHovered ? 'bold ' : '') + '10px "JetBrains Mono", monospace'
    ctx.fillText(String(dayNum), x, h - CHART_PADDING_BOTTOM + 6)

    // Weekday abbreviation under the number
    ctx.fillStyle = isToday ? '#6366f1' : '#2e3350'
    ctx.font = '8px "JetBrains Mono", monospace'
    ctx.fillText(WEEKDAY_NAMES[wd] ?? '', x, h - CHART_PADDING_BOTTOM + 18)

    // Today marker
    if (isToday) {
      ctx.strokeStyle = '#6366f1'
      ctx.lineWidth = 1.5
      ctx.setLineDash([3, 3])
      ctx.beginPath()
      ctx.moveTo(x, CHART_PADDING_TOP)
      ctx.lineTo(x, h - CHART_PADDING_BOTTOM)
      ctx.stroke()
      ctx.setLineDash([])
    }

    // Small dot at day label area to indicate transactions exist
    if (hasTxns) {
      ctx.beginPath()
      ctx.arc(x, h - CHART_PADDING_BOTTOM + 2, 1.5, 0, Math.PI * 2)
      ctx.fillStyle = d.net_k > 0 ? '#22c55e' : '#ef4444'
      ctx.fill()
    }
  }

  // --- Balance bars ---
  const barGap = 2
  const barW = DAY_WIDTH - barGap * 2
  const baseY = zeroVisible ? zeroY : h - CHART_PADDING_BOTTOM

  for (let i = firstVisible; i <= lastVisible; i++) {
    const x = xForIndex(i)
    const bucket = days[i]!
    const balY = yForBalance(bucket.balance_k, h)
    const isHov = i === hIdx

    if (bucket.balance_k >= 0) {
      const top = Math.min(balY, baseY)
      const barH = Math.abs(baseY - balY)
      ctx.fillStyle = isHov ? 'rgba(129, 140, 248, 0.55)' : 'rgba(99, 102, 241, 0.35)'
      ctx.fillRect(x - barW / 2, top, barW, barH)
      ctx.strokeStyle = isHov ? '#a5b4fc' : '#818cf8'
      ctx.lineWidth = isHov ? 1.5 : 0.5
      ctx.strokeRect(x - barW / 2, top, barW, barH)
    } else {
      const top = baseY
      const barH = Math.abs(balY - baseY)
      ctx.fillStyle = isHov ? 'rgba(239, 68, 68, 0.55)' : 'rgba(239, 68, 68, 0.35)'
      ctx.fillRect(x - barW / 2, top, barW, barH)
      ctx.strokeStyle = isHov ? '#fca5a5' : '#ef4444'
      ctx.lineWidth = isHov ? 1.5 : 0.5
      ctx.strokeRect(x - barW / 2, top, barW, barH)
    }
  }

  // --- Zero line — solid red, drawn on top of bars ---
  if (zeroVisible) {
    ctx.strokeStyle = '#ef4444'
    ctx.lineWidth = 2
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.moveTo(CHART_PADDING_LEFT, zeroY)
    ctx.lineTo(w, zeroY)
    ctx.stroke()
  }

  // Hovered day Y-axis badge
  if (hIdx !== null && hIdx >= firstVisible && hIdx <= lastVisible) {
    const hBucket = days[hIdx]!
    const hy = yForBalance(hBucket.balance_k, h)

    // Horizontal crosshair
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)'
    ctx.lineWidth = 1
    ctx.setLineDash([2, 2])
    ctx.beginPath()
    ctx.moveTo(CHART_PADDING_LEFT, hy)
    ctx.lineTo(w, hy)
    ctx.stroke()
    ctx.setLineDash([])

    // Y-axis label badge
    ctx.fillStyle = '#818cf8'
    ctx.fillRect(0, hy - 10, CHART_PADDING_LEFT - 4, 20)
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 10px "JetBrains Mono", monospace'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'
    ctx.fillText(formatK(hBucket.balance_k), CHART_PADDING_LEFT - 8, hy)
  }

  // Global min markers (triangle)
  for (const minDate of props.globalMinDates) {
    const idx = days.findIndex(d => d.date === minDate)
    if (idx < firstVisible || idx > lastVisible) continue
    const mBucket = days[idx]!
    const mx = xForIndex(idx)
    const my = yForBalance(mBucket.balance_k, h)
    ctx.beginPath()
    ctx.moveTo(mx, my - 8)
    ctx.lineTo(mx - 5, my - 14)
    ctx.lineTo(mx + 5, my - 14)
    ctx.closePath()
    ctx.fillStyle = mBucket.balance_k < 0 ? '#ef4444' : '#f59e0b'
    ctx.fill()
  }
}

function formatK(val: number): string {
  if (Math.abs(val) >= 1000) return (val / 1000).toFixed(1) + 'M'
  return val.toFixed(1) + 'k'
}

function niceGridSteps(min: number, max: number, target: number): number[] {
  const range = max - min
  if (range <= 0) return [0]
  const rough = range / target
  const mag = Math.pow(10, Math.floor(Math.log10(rough)))
  let step = mag
  if (rough / mag >= 5) step = mag * 5
  else if (rough / mag >= 2) step = mag * 2

  const steps: number[] = []
  let v = Math.ceil(min / step) * step
  while (v <= max) {
    steps.push(Math.round(v * 1000) / 1000)
    v += step
  }
  return steps
}

function formatDateForTooltip(iso: string): string {
  const [, mo, dy] = parseDateParts(iso)
  const wd = weekday(iso)
  return (WEEKDAY_NAMES[wd] ?? '') + ', ' + (MONTH_NAMES[parseInt(mo) - 1] ?? '') + ' ' + parseInt(dy)
}

// --- Scroll / pan with momentum ---

function clampScroll() {
  if (!containerRef.value) return
  const maxScroll = Math.max(0, totalWidth.value - containerRef.value.clientWidth)
  scrollX.value = Math.max(0, Math.min(scrollX.value, maxScroll))
}

function centerOnToday() {
  if (!containerRef.value) return
  const todayIdx = props.days.findIndex(d => d.date === today)
  if (todayIdx < 0) return
  const viewW = containerRef.value.clientWidth
  scrollX.value = CHART_PADDING_LEFT + todayIdx * DAY_WIDTH - viewW * 0.37
  clampScroll()
}

function onPointerDown(e: PointerEvent) {
  isDragging.value = true
  dragStartX = e.clientX
  dragStartScroll = scrollX.value
  lastDragX = e.clientX
  lastDragTime = performance.now()
  velocityX = 0
  cancelAnimationFrame(animFrame)
  ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  const idx = indexForClientX(e.clientX)
  if (!isDragging.value) {
    hoveredIndex.value = idx
    draw()
    return
  }

  const now = performance.now()
  const dt = now - lastDragTime
  const dx = e.clientX - lastDragX
  if (dt > 0) velocityX = dx / dt

  lastDragX = e.clientX
  lastDragTime = now

  scrollX.value = dragStartScroll - (e.clientX - dragStartX)
  clampScroll()
  hoveredIndex.value = idx
  draw()
}

function onPointerUp(e: PointerEvent) {
  if (!isDragging.value) return
  isDragging.value = false
  ;(e.target as HTMLElement).releasePointerCapture(e.pointerId)

  const dist = Math.abs(e.clientX - dragStartX)
  if (dist < 4) {
    const idx = indexForClientX(e.clientX)
    if (idx !== null) {
      selectedIndex.value = idx
      emit('selectDay', props.days[idx]!.date)
    }
    draw()
    return
  }

  if (Math.abs(velocityX) > 0.1) {
    const friction = 0.95
    const tick = () => {
      velocityX *= friction
      scrollX.value -= velocityX * 16
      clampScroll()
      draw()
      if (Math.abs(velocityX) > 0.05) animFrame = requestAnimationFrame(tick)
    }
    animFrame = requestAnimationFrame(tick)
  }
}

function onPointerLeave() {
  if (!isDragging.value) {
    hoveredIndex.value = null
    draw()
  }
}

function onWheel(e: WheelEvent) {
  scrollX.value += e.deltaX || e.deltaY
  clampScroll()
  draw()
}

function onKeyDown(e: KeyboardEvent) {
  const current = selectedIndex.value ?? hoveredIndex.value
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    const next = current !== null ? Math.min(current + 1, props.days.length - 1) : 0
    selectedIndex.value = next
    ensureVisible(next)
    emit('selectDay', props.days[next]!.date)
    draw()
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    const prev = current !== null ? Math.max(current - 1, 0) : 0
    selectedIndex.value = prev
    ensureVisible(prev)
    emit('selectDay', props.days[prev]!.date)
    draw()
  } else if (e.key === 'Enter' && current !== null) {
    emit('selectDay', props.days[current]!.date)
  }
}

function ensureVisible(idx: number) {
  if (!containerRef.value) return
  const x = CHART_PADDING_LEFT + idx * DAY_WIDTH
  const viewW = containerRef.value.clientWidth
  if (x - scrollX.value < CHART_PADDING_LEFT + 20) {
    scrollX.value = x - CHART_PADDING_LEFT - 40
  } else if (x - scrollX.value > viewW - 40) {
    scrollX.value = x - viewW + 60
  }
  clampScroll()
}

let resizeObs: ResizeObserver | null = null

onMounted(() => {
  centerOnToday()
  draw()
  resizeObs = new ResizeObserver(() => draw())
  if (containerRef.value) resizeObs.observe(containerRef.value)
})

onUnmounted(() => {
  cancelAnimationFrame(animFrame)
  resizeObs?.disconnect()
})

watch(
  [() => props.days, () => props.globalMin, () => props.globalMinDates, () => props.firstNegativeDate],
  () => draw(),
)

defineExpose({ centerOnToday })
</script>

<template>
  <div
    ref="containerRef"
    class="relative w-full h-full select-none outline-none"
    tabindex="0"
    @keydown="onKeyDown"
  >
    <canvas
      ref="canvasRef"
      class="absolute inset-0 cursor-crosshair"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerLeave"
      @wheel.prevent="onWheel"
    />

    <!-- Hover tooltip: day date + balance + transaction list -->
    <Transition name="fade">
      <div
        v-if="activeDay"
        class="absolute top-2 right-2 bg-[#181b28]/95 border border-[#2a2f45] rounded-lg px-4 py-3 shadow-xl pointer-events-none z-10 min-w-[200px] max-w-[280px]"
      >
        <div class="text-xs text-slate-400 font-mono mb-1.5 tracking-wide">
          {{ formatDateForTooltip(activeDay.date) }}
        </div>
        <div class="text-xl font-mono font-bold mb-1" :class="activeDay.balance_k < 0 ? 'text-red-400' : 'text-indigo-300'">
          {{ formatK(activeDay.balance_k) }}
          <span class="text-[10px] font-normal text-slate-500 ml-1">EOD balance</span>
        </div>

        <div v-if="activeDay.net_k !== 0" class="text-xs font-mono mb-2 flex items-center gap-1.5">
          <span class="text-slate-500">Day net:</span>
          <span class="font-bold" :class="activeDay.net_k > 0 ? 'text-emerald-400' : 'text-red-400'">
            {{ activeDay.net_k > 0 ? '+' : '' }}{{ activeDay.net_k.toFixed(2) }}k
          </span>
        </div>

        <!-- Transaction list for this day -->
        <div v-if="activeDay.transactions.length" class="border-t border-[#2a2f45] pt-2 mt-1">
          <div class="text-[10px] text-slate-500 font-mono mb-1.5 uppercase tracking-wider">
            Transactions ({{ activeDay.transactions.length }})
          </div>
          <div class="space-y-1">
            <div
              v-for="txn in activeDay.transactions.slice(0, 6)"
              :key="txn.id"
              class="flex justify-between gap-3 items-baseline"
            >
              <span class="text-[11px] font-mono text-slate-300 truncate">{{ txn.description }}</span>
              <span class="text-[11px] font-mono font-bold shrink-0" :class="txn.amount_k > 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ txn.amount_k > 0 ? '+' : '' }}{{ txn.amount_k.toFixed(1) }}k
              </span>
            </div>
          </div>
          <div v-if="activeDay.transactions.length > 6" class="text-[10px] text-slate-500 font-mono mt-1">
            +{{ activeDay.transactions.length - 6 }} more
          </div>
        </div>
        <div v-else class="text-[10px] text-slate-600 font-mono mt-1 italic">
          No transactions
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
