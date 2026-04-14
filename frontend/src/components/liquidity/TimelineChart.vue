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

const DAY_WIDTH = 18
const CHART_PADDING_TOP = 40
const CHART_PADDING_BOTTOM = 60
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

  // Horizontal grid lines
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

  // Zero line
  const zeroY = yForBalance(0, h)
  if (zeroY >= CHART_PADDING_TOP && zeroY <= h - CHART_PADDING_BOTTOM) {
    ctx.strokeStyle = '#3a3f55'
    ctx.lineWidth = 1.5
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(CHART_PADDING_LEFT, zeroY)
    ctx.lineTo(w, zeroY)
    ctx.stroke()
    ctx.setLineDash([])
  }

  // Negative region fill
  if (min < 0) {
    const negBottom = Math.min(yForBalance(min, h), h - CHART_PADDING_BOTTOM)
    const negTop = Math.max(zeroY, CHART_PADDING_TOP)
    ctx.fillStyle = 'rgba(239, 68, 68, 0.06)'
    ctx.fillRect(CHART_PADDING_LEFT, negTop, w - CHART_PADDING_LEFT, negBottom - negTop)
  }

  // Day columns — vertical lines for months + date labels
  const firstVisible = Math.max(0, Math.floor((scrollX.value - CHART_PADDING_LEFT) / DAY_WIDTH))
  const lastVisible = Math.min(days.length - 1, firstVisible + Math.ceil(w / DAY_WIDTH) + 2)

  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'

  let lastLabelMonth = ''
  for (let i = firstVisible; i <= lastVisible; i++) {
    const x = xForIndex(i)
    if (x < CHART_PADDING_LEFT || x > w) continue
    const d = days[i]!
    const [yr, mo, dy] = parseDateParts(d.date)
    const monthKey = yr + '-' + mo
    const dayNum = parseInt(dy)

    if (monthKey !== lastLabelMonth && dayNum <= 7) {
      ctx.strokeStyle = '#2a2f45'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(x, CHART_PADDING_TOP)
      ctx.lineTo(x, h - CHART_PADDING_BOTTOM)
      ctx.stroke()

      const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
      const mIdx = parseInt(mo) - 1
      ctx.fillStyle = '#7c82a0'
      ctx.font = '10px "JetBrains Mono", monospace'
      ctx.fillText((monthNames[mIdx] ?? '') + ' ' + yr.slice(2), x + 20, h - CHART_PADDING_BOTTOM + 24)
      lastLabelMonth = monthKey
    }

    if (dayNum === 1 || dayNum === 8 || dayNum === 15 || dayNum === 22) {
      ctx.fillStyle = '#5c6078'
      ctx.font = '9px "JetBrains Mono", monospace'
      ctx.fillText(String(dayNum), x, h - CHART_PADDING_BOTTOM + 8)
    }

    if (d.date === today) {
      ctx.strokeStyle = '#6366f1'
      ctx.lineWidth = 1.5
      ctx.setLineDash([3, 3])
      ctx.beginPath()
      ctx.moveTo(x, CHART_PADDING_TOP)
      ctx.lineTo(x, h - CHART_PADDING_BOTTOM)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.fillStyle = '#6366f1'
      ctx.font = 'bold 9px "JetBrains Mono", monospace'
      ctx.fillText('TODAY', x, h - CHART_PADDING_BOTTOM + 42)
    }

    if (d.net_k !== 0) {
      ctx.fillStyle = d.net_k > 0 ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)'
      const barH = Math.min(Math.abs(d.net_k) / (max - min) * plotH * 0.5, plotH * 0.15)
      const barY = d.net_k > 0
        ? yForBalance(d.balance_k, h) - barH
        : yForBalance(d.balance_k, h)
      ctx.fillRect(x - DAY_WIDTH / 2 + 2, barY, DAY_WIDTH - 4, barH)
    }
  }

  // Balance line — gradient fill under the line
  ctx.beginPath()
  let started = false
  for (let i = firstVisible; i <= lastVisible; i++) {
    const x = xForIndex(i)
    const y = yForBalance(days[i]!.balance_k, h)
    if (!started) { ctx.moveTo(x, y); started = true }
    else ctx.lineTo(x, y)
  }

  if (started && lastVisible > firstVisible) {
    const lastX = xForIndex(lastVisible)
    const firstX = xForIndex(firstVisible)
    ctx.lineTo(lastX, h - CHART_PADDING_BOTTOM)
    ctx.lineTo(firstX, h - CHART_PADDING_BOTTOM)
    ctx.closePath()

    const grad = ctx.createLinearGradient(0, CHART_PADDING_TOP, 0, h - CHART_PADDING_BOTTOM)
    grad.addColorStop(0, 'rgba(99, 102, 241, 0.15)')
    grad.addColorStop(0.7, 'rgba(99, 102, 241, 0.03)')
    grad.addColorStop(1, 'rgba(99, 102, 241, 0)')
    ctx.fillStyle = grad
    ctx.fill()
  }

  // Balance line stroke
  ctx.beginPath()
  started = false
  for (let i = firstVisible; i <= lastVisible; i++) {
    const x = xForIndex(i)
    const y = yForBalance(days[i]!.balance_k, h)
    if (!started) { ctx.moveTo(x, y); started = true }
    else ctx.lineTo(x, y)
  }
  ctx.strokeStyle = '#818cf8'
  ctx.lineWidth = 2
  ctx.stroke()

  // Negative segments in red
  ctx.beginPath()
  started = false
  for (let i = firstVisible; i <= lastVisible; i++) {
    const x = xForIndex(i)
    const bucket = days[i]!
    const y = yForBalance(bucket.balance_k, h)
    if (bucket.balance_k < 0) {
      if (!started) { ctx.moveTo(x, y); started = true }
      else ctx.lineTo(x, y)
    } else {
      if (started) {
        ctx.strokeStyle = '#ef4444'
        ctx.lineWidth = 2.5
        ctx.stroke()
        ctx.beginPath()
        started = false
      }
    }
  }
  if (started) {
    ctx.strokeStyle = '#ef4444'
    ctx.lineWidth = 2.5
    ctx.stroke()
  }

  // Hovered day crosshair + dot
  const hIdx = hoveredIndex.value ?? selectedIndex.value
  if (hIdx !== null && hIdx >= firstVisible && hIdx <= lastVisible) {
    const hBucket = days[hIdx]!
    const hx = xForIndex(hIdx)
    const hy = yForBalance(hBucket.balance_k, h)

    ctx.strokeStyle = 'rgba(148, 163, 184, 0.3)'
    ctx.lineWidth = 1
    ctx.setLineDash([2, 2])
    ctx.beginPath()
    ctx.moveTo(hx, CHART_PADDING_TOP)
    ctx.lineTo(hx, h - CHART_PADDING_BOTTOM)
    ctx.stroke()
    ctx.setLineDash([])

    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)'
    ctx.lineWidth = 1
    ctx.setLineDash([2, 2])
    ctx.beginPath()
    ctx.moveTo(CHART_PADDING_LEFT, hy)
    ctx.lineTo(w, hy)
    ctx.stroke()
    ctx.setLineDash([])

    ctx.beginPath()
    ctx.arc(hx, hy, 5, 0, Math.PI * 2)
    ctx.fillStyle = hBucket.balance_k < 0 ? '#ef4444' : '#818cf8'
    ctx.fill()
    ctx.strokeStyle = '#0f1117'
    ctx.lineWidth = 2
    ctx.stroke()

    // Y-axis label
    ctx.fillStyle = '#818cf8'
    ctx.fillRect(0, hy - 10, CHART_PADDING_LEFT - 4, 20)
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 10px "JetBrains Mono", monospace'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'
    ctx.fillText(formatK(hBucket.balance_k), CHART_PADDING_LEFT - 8, hy)

    // Date label at bottom
    ctx.fillStyle = '#818cf8'
    const dateLabel = formatDateLabel(hBucket.date)
    const tw = ctx.measureText(dateLabel).width + 12
    ctx.fillRect(hx - tw / 2, h - CHART_PADDING_BOTTOM + 2, tw, 18)
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 9px "JetBrains Mono", monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(dateLabel, hx, h - CHART_PADDING_BOTTOM + 11)
  }

  // Global min markers
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

function formatDateLabel(iso: string): string {
  const [, m, d] = parseDateParts(iso)
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return (months[parseInt(m) - 1] ?? '') + ' ' + parseInt(d)
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

watch(() => [props.days, props.globalMin], () => draw(), { deep: true })

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

    <!-- Hover tooltip -->
    <Transition name="fade">
      <div
        v-if="activeDay"
        class="absolute top-2 right-2 bg-[#181b28]/95 border border-[#2a2f45] rounded-lg px-3 py-2 shadow-xl pointer-events-none z-10 min-w-[180px]"
      >
        <div class="text-[11px] text-slate-400 font-mono mb-1">
          {{ activeDay.date }}
        </div>
        <div class="text-lg font-mono font-bold" :class="activeDay.balance_k < 0 ? 'text-red-400' : 'text-indigo-300'">
          {{ formatK(activeDay.balance_k) }}
        </div>
        <div v-if="activeDay.net_k !== 0" class="text-xs font-mono mt-1" :class="activeDay.net_k > 0 ? 'text-emerald-400' : 'text-red-400'">
          net: {{ activeDay.net_k > 0 ? '+' : '' }}{{ activeDay.net_k.toFixed(2) }}k
        </div>
        <div v-if="activeDay.transactions.length" class="mt-1 border-t border-[#2a2f45] pt-1">
          <div
            v-for="txn in activeDay.transactions.slice(0, 4)"
            :key="txn.id"
            class="text-[10px] font-mono text-slate-400 flex justify-between gap-3"
          >
            <span class="truncate max-w-[120px]">{{ txn.description }}</span>
            <span :class="txn.amount_k > 0 ? 'text-emerald-400' : 'text-red-400'">
              {{ txn.amount_k > 0 ? '+' : '' }}{{ txn.amount_k.toFixed(1) }}k
            </span>
          </div>
          <div v-if="activeDay.transactions.length > 4" class="text-[10px] text-slate-500">
            +{{ activeDay.transactions.length - 4 }} more
          </div>
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
