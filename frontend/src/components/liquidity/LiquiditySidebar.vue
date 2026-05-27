<script setup lang="ts">
import { computed } from 'vue'
import type {
  LiquiditySeries,
  LiquidityTransaction,
  LiquidityRecurringTransaction,
  LiquiditySettings,
  MercuryBalanceResponse,
} from '../../types/liquidity'
import { todayISO, addDays, describeRecurrence } from '../../utils/liquidityEngine'

const props = defineProps<{
  series: LiquiditySeries
  settings: LiquiditySettings
  transactions: LiquidityTransaction[]
  recurringRules?: LiquidityRecurringTransaction[]
  mercuryBalance?: MercuryBalanceResponse | null
  mercurySyncing?: boolean
  mercuryError?: string | null
  mercuryLastSyncedAt?: string | null
}>()

const emit = defineEmits<{
  (e: 'editRecurring', ruleId: string): void
  (e: 'deleteRecurring', ruleId: string): void
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

const activeRecurringRules = computed(() => {
  const list = props.recurringRules ?? []
  // Sort outflows first so the most "interesting" series (HM interest,
  // mortgage payments) bubble up. Inside each group keep start-date order.
  return [...list].sort((a, b) => {
    const aOut = a.amount_k < 0 ? 0 : 1
    const bOut = b.amount_k < 0 ? 0 : 1
    if (aOut !== bOut) return aOut - bOut
    return a.start_date.localeCompare(b.start_date)
  })
})

function endLabel(rule: LiquidityRecurringTransaction): string {
  if (rule.end_date) return 'until ' + formatDate(rule.end_date)
  if (rule.occurrences) return rule.occurrences + 'x'
  return 'no end'
}
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
          <i class="pi pi-exclamation-triangle text-[9px]"></i>
          {{ mercuryBalance && mercuryBalance.workspaces.length > 0 ? 'partial sync' : 'mercury offline' }}
        </div>
        <div
          v-else-if="mercuryBalance"
          class="flex items-center gap-1 text-[10px] text-emerald-400"
          :title="`Synced ${mercuryBalance.account_count} account(s) across ${mercuryBalance.workspace_count} workspace(s)` + (mercurySyncedTime ? ' at ' + mercurySyncedTime : '')"
        >
          <i class="pi pi-check-circle text-[9px]"></i>
          mercury · {{ mercuryBalance.workspace_count }}
        </div>
      </div>
      <div class="text-xl font-bold" :class="todayBalance !== null && todayBalance < 0 ? 'text-red-400' : 'text-indigo-300'">
        {{ todayBalance !== null ? todayBalance.toFixed(1) + 'k' : '—' }}
      </div>

      <!-- Per-workspace breakdown -->
      <div
        v-if="mercuryBalance && mercuryBalance.workspaces.length > 0"
        class="mt-2 pt-2 border-t border-[#2a2f45] space-y-2"
      >
        <div v-for="ws in mercuryBalance.workspaces" :key="ws.workspace" class="space-y-0.5">
          <div class="flex items-center justify-between text-[10px]">
            <span class="text-slate-300 font-semibold uppercase tracking-wide">{{ ws.workspace }}</span>
            <span class="text-slate-300 whitespace-nowrap">{{ ws.total_balance_k.toFixed(1) }}k</span>
          </div>
          <div
            v-for="a in ws.accounts"
            :key="a.id"
            class="flex items-center justify-between text-[10px] text-slate-500 pl-2"
          >
            <span class="truncate pr-1">{{ a.name || a.type || 'Account' }}</span>
            <span class="text-slate-400 whitespace-nowrap">{{ a.current_balance_k.toFixed(1) }}k</span>
          </div>
        </div>
      </div>

      <!-- Per-workspace errors -->
      <div
        v-if="mercuryBalance && mercuryBalance.workspace_errors.length > 0"
        class="mt-2 pt-2 border-t border-[#2a2f45] space-y-0.5"
      >
        <div
          v-for="err in mercuryBalance.workspace_errors"
          :key="err.workspace"
          class="flex items-center justify-between text-[10px] text-red-400"
          :title="err.error"
        >
          <span class="font-semibold uppercase tracking-wide">{{ err.workspace }}</span>
          <span class="truncate pl-2">{{ err.error }}</span>
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

    <!-- Recurring series -->
    <div
      v-if="activeRecurringRules.length > 0"
      class="bg-[#1a1d2e] rounded-lg p-3 border border-[#2a2f45]"
    >
      <div class="flex items-center justify-between mb-2">
        <div class="text-slate-500 flex items-center gap-1.5">
          <i class="pi pi-refresh text-[10px] text-indigo-400"></i>
          Recurring
        </div>
        <div class="text-[10px] text-slate-500">{{ activeRecurringRules.length }}</div>
      </div>
      <div class="space-y-1.5">
        <div
          v-for="rule in activeRecurringRules"
          :key="rule.id"
          class="rounded-lg bg-[#141722] border border-[#2a2f45] px-2 py-1.5 group"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="text-[11px] text-slate-200 truncate" :title="rule.description">
              {{ rule.description }}
            </div>
            <div
              class="text-[11px] font-bold shrink-0"
              :class="rule.amount_k > 0 ? 'text-emerald-400' : 'text-red-400'"
            >
              {{ rule.amount_k > 0 ? '+' : '' }}{{ rule.amount_k.toFixed(1) }}k
            </div>
          </div>
          <div class="flex items-center justify-between mt-0.5">
            <div class="text-[9px] text-slate-500 truncate">
              {{ describeRecurrence(rule) }} · {{ endLabel(rule) }}
            </div>
            <div class="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
              <button
                class="w-5 h-5 flex items-center justify-center rounded text-slate-500 hover:text-indigo-400 hover:bg-indigo-500/10 transition-all"
                title="Edit series"
                @click="emit('editRecurring', rule.id)"
              >
                <i class="pi pi-pencil text-[9px]"></i>
              </button>
              <button
                class="w-5 h-5 flex items-center justify-center rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                title="Delete series"
                @click="emit('deleteRecurring', rule.id)"
              >
                <i class="pi pi-trash text-[9px]"></i>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
