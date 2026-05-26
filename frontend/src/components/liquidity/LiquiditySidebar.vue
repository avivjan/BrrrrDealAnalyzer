<script setup lang="ts">
import { computed } from 'vue'
import type {
  LiquiditySeries,
  LiquidityTransaction,
  LiquiditySettings,
  MercuryBalanceResponse,
} from '../../types/liquidity'
import { todayISO, addDays } from '../../utils/liquidityEngine'

const props = defineProps<{
  series: LiquiditySeries
  settings: LiquiditySettings
  transactions: LiquidityTransaction[]
  mercuryBalance?: MercuryBalanceResponse | null
  mercurySyncing?: boolean
  mercuryError?: string | null
  mercuryLastSyncedAt?: string | null
}>()

const today = todayISO()

function formatDate(iso: string): string {
  const parts = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return (months[parseInt(parts[1] ?? '0') - 1] ?? '') + ' ' + parseInt(parts[2] ?? '0')
}

const todayBalance = computed(() => {
  const bucket = props.series.days.find(d => d.date === today)
  return bucket?.balance_k ?? null
})

const mercurySyncedTime = computed(() => {
  if (!props.mercuryLastSyncedAt) return null
  const d = new Date(props.mercuryLastSyncedAt)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
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
      <div class="flex items-center justify-between mb-1">
        <div class="text-slate-500">Today's Balance</div>
        <div v-if="mercurySyncing" class="flex items-center gap-1 text-[10px] text-slate-500">
          <i class="pi pi-spin pi-spinner text-[9px]"></i> syncing
        </div>
        <div
          v-else-if="mercuryError"
          class="flex items-center gap-1 text-[10px] text-red-400"
          :title="mercuryError"
        >
          <i class="pi pi-exclamation-triangle text-[9px]"></i> mercury offline
        </div>
        <div
          v-else-if="mercuryBalance"
          class="flex items-center gap-1 text-[10px] text-emerald-400"
          :title="`Synced ${mercuryBalance.account_count} Mercury account(s)` + (mercurySyncedTime ? ' at ' + mercurySyncedTime : '')"
        >
          <i class="pi pi-check-circle text-[9px]"></i> mercury
        </div>
      </div>
      <div class="text-xl font-bold" :class="todayBalance !== null && todayBalance < 0 ? 'text-red-400' : 'text-indigo-300'">
        {{ todayBalance !== null ? todayBalance.toFixed(1) + 'k' : '—' }}
      </div>
      <div
        v-if="mercuryBalance && mercuryBalance.accounts.length > 0"
        class="mt-2 pt-2 border-t border-[#2a2f45] space-y-0.5"
      >
        <div
          v-for="a in mercuryBalance.accounts"
          :key="a.id"
          class="flex items-center justify-between text-[10px] text-slate-500"
        >
          <span class="truncate pr-1">{{ a.name || a.type || 'Account' }}</span>
          <span class="text-slate-400 whitespace-nowrap">{{ a.current_balance_k.toFixed(1) }}k</span>
        </div>
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
