<script setup lang="ts">
import { computed } from 'vue'
import type { LiquiditySeries, LiquidityTransaction, LiquiditySettings } from '../../types/liquidity'
import { todayISO, addDays } from '../../utils/liquidityEngine'

const props = defineProps<{
  series: LiquiditySeries
  settings: LiquiditySettings
  transactions: LiquidityTransaction[]
}>()

const today = todayISO()

function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return months[parseInt(m) - 1] + ' ' + parseInt(d)
}

const todayBalance = computed(() => {
  const bucket = props.series.days.find(d => d.date === today)
  return bucket?.balance_k ?? null
})

const next90dMin = computed(() => {
  const end = addDays(today, 90)
  let min = Infinity
  let minDate = ''
  for (const d of props.series.days) {
    if (d.date >= today && d.date <= end) {
      if (d.balance_k < min) { min = d.balance_k; minDate = d.date }
    }
  }
  return min === Infinity ? null : { value: min, date: minDate }
})

const nextOutflow = computed(() => {
  const future = props.transactions
    .filter(t => t.amount_k < 0 && t.effective_date >= today)
    .sort((a, b) => a.effective_date.localeCompare(b.effective_date))
  return future[0] ?? null
})

const nextInflow = computed(() => {
  const future = props.transactions
    .filter(t => t.amount_k > 0 && t.effective_date >= today)
    .sort((a, b) => a.effective_date.localeCompare(b.effective_date))
  return future[0] ?? null
})
</script>

<template>
  <div class="flex flex-col gap-3 text-xs font-mono">
    <!-- Today's balance -->
    <div class="bg-[#1a1d2e] rounded-lg p-3 border border-[#2a2f45]">
      <div class="text-slate-500 mb-1">Today's Balance</div>
      <div class="text-xl font-bold" :class="todayBalance !== null && todayBalance < 0 ? 'text-red-400' : 'text-indigo-300'">
        {{ todayBalance !== null ? todayBalance.toFixed(1) + 'k' : '—' }}
      </div>
    </div>

    <!-- Window min -->
    <div class="bg-[#1a1d2e] rounded-lg p-3 border border-[#2a2f45]">
      <div class="text-slate-500 mb-1">Window Min</div>
      <div class="font-bold" :class="series.globalMin < 0 ? 'text-red-400' : series.globalMin < settings.reserve_k ? 'text-amber-400' : 'text-slate-200'">
        {{ series.globalMin.toFixed(1) }}k
      </div>
      <div class="text-slate-500 mt-0.5">
        on {{ series.globalMinDates.slice(0, 2).map(formatDate).join(', ') }}
        <span v-if="series.globalMinDates.length > 2"> +{{ series.globalMinDates.length - 2 }}</span>
      </div>
    </div>

    <!-- 90d low -->
    <div v-if="next90dMin" class="bg-[#1a1d2e] rounded-lg p-3 border border-[#2a2f45]">
      <div class="text-slate-500 mb-1">Low (next 90d)</div>
      <div class="font-bold" :class="next90dMin.value < 0 ? 'text-red-400' : 'text-slate-200'">
        {{ next90dMin.value.toFixed(1) }}k
      </div>
      <div class="text-slate-500 mt-0.5">{{ formatDate(next90dMin.date) }}</div>
    </div>

    <!-- Next outflow -->
    <div v-if="nextOutflow" class="bg-[#1a1d2e] rounded-lg p-3 border border-[#2a2f45]">
      <div class="text-slate-500 mb-1">Next Outflow</div>
      <div class="text-red-400 font-bold">{{ nextOutflow.amount_k.toFixed(1) }}k</div>
      <div class="text-slate-500 mt-0.5 truncate">{{ nextOutflow.description }}</div>
      <div class="text-slate-500">{{ formatDate(nextOutflow.effective_date) }}</div>
    </div>

    <!-- Next inflow -->
    <div v-if="nextInflow" class="bg-[#1a1d2e] rounded-lg p-3 border border-[#2a2f45]">
      <div class="text-slate-500 mb-1">Next Inflow</div>
      <div class="text-emerald-400 font-bold">+{{ nextInflow.amount_k.toFixed(1) }}k</div>
      <div class="text-slate-500 mt-0.5 truncate">{{ nextInflow.description }}</div>
      <div class="text-slate-500">{{ formatDate(nextInflow.effective_date) }}</div>
    </div>

    <!-- Reserve -->
    <div class="bg-[#1a1d2e] rounded-lg p-3 border border-[#2a2f45]">
      <div class="text-slate-500 mb-1">Reserve Threshold</div>
      <div class="text-slate-200 font-bold">{{ settings.reserve_k.toFixed(1) }}k</div>
    </div>
  </div>
</template>
