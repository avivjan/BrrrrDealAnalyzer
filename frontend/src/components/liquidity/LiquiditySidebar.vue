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
  <!--
    The section titles are card labels, not page headings: one arbitrary
    variant here sizes and tones every `UiSectionHeader` title below,
    instead of repeating a class on all seven.
  -->
  <div class="grid grid-cols-1 gap-3 text-xs sm:grid-cols-2 lg:grid-cols-1 [&_[data-part=title]]:text-[11px] [&_[data-part=title]]:text-fg-muted">
    <!-- Today's balance -->
    <UiCard padding="sm">
      <UiSectionHeader as="h4" class="mb-1">
        Today's Balance
        <template #actions>
          <div v-if="mercurySyncing" class="flex items-center gap-1 text-[10px] text-fg-muted">
            <i class="pi pi-spin pi-spinner text-[9px]" aria-hidden="true"></i> syncing
          </div>
          <div
            v-else-if="mercuryError"
            class="flex items-center gap-1 text-[10px] text-negative"
            :title="mercuryError"
          >
            <i class="pi pi-exclamation-triangle text-[9px]" aria-hidden="true"></i>
            {{ mercuryBalance && mercuryBalance.workspaces.length > 0 ? 'partial sync' : 'mercury offline' }}
          </div>
          <div
            v-else-if="mercuryBalance"
            class="flex items-center gap-1 text-[10px] text-positive"
            :title="`Synced ${mercuryBalance.account_count} account(s) across ${mercuryBalance.workspace_count} workspace(s)` + (mercurySyncedTime ? ' at ' + mercurySyncedTime : '')"
          >
            <i class="pi pi-check-circle text-[9px]" aria-hidden="true"></i>
            mercury · {{ mercuryBalance.workspace_count }}
          </div>
        </template>
      </UiSectionHeader>
      <div class="text-xl font-bold tabular" :class="todayBalance !== null && todayBalance < 0 ? 'text-negative' : 'text-primary'">
        {{ todayBalance !== null ? todayBalance.toFixed(1) + 'k' : '—' }}
      </div>

      <!-- Per-workspace breakdown -->
      <div
        v-if="mercuryBalance && mercuryBalance.workspaces.length > 0"
        class="mt-2 space-y-2 border-t border-line pt-2"
      >
        <div v-for="ws in mercuryBalance.workspaces" :key="ws.workspace" :data-testid="`sidebar.workspace.${ws.workspace}`" class="space-y-0.5">
          <div class="flex items-center justify-between gap-2 text-[10px]">
            <span class="min-w-0 truncate font-semibold uppercase tracking-wide text-fg">{{ ws.workspace }}</span>
            <span class="whitespace-nowrap tabular text-fg">{{ ws.total_balance_k.toFixed(1) }}k</span>
          </div>
          <div
            v-for="a in ws.accounts"
            :key="a.id"
            :data-testid="`sidebar.account.${a.id}`"
            class="flex items-center justify-between gap-2 pl-2 text-[10px] text-fg-muted"
          >
            <span class="min-w-0 truncate pr-1">{{ a.name || a.type || 'Account' }}</span>
            <span class="whitespace-nowrap tabular text-fg-muted">{{ a.current_balance_k.toFixed(1) }}k</span>
          </div>
        </div>
      </div>

      <!-- Per-workspace errors -->
      <div
        v-if="mercuryBalance && mercuryBalance.workspace_errors.length > 0"
        class="mt-2 space-y-0.5 border-t border-line pt-2"
      >
        <div
          v-for="err in mercuryBalance.workspace_errors"
          :key="err.workspace"
          :data-testid="`sidebar.workspace-error.${err.workspace}`"
          class="flex items-center justify-between gap-2 text-[10px] text-negative"
          :title="err.error"
        >
          <span class="font-semibold uppercase tracking-wide">{{ err.workspace }}</span>
          <span class="min-w-0 truncate pl-2">{{ err.error }}</span>
        </div>
      </div>
    </UiCard>

    <!-- Window min -->
    <UiCard padding="sm">
      <UiSectionHeader as="h4" class="mb-1">Window Min</UiSectionHeader>
      <div class="font-bold tabular" :class="series.globalMin < 0 ? 'text-negative' : series.globalMin < settings.reserve_k ? 'text-warning' : 'text-fg'">
        {{ series.globalMin.toFixed(1) }}k
      </div>
      <div class="mt-0.5 text-fg-muted">
        on {{ series.globalMinDates.slice(0, 2).map(formatDate).join(', ') }}
        <span v-if="series.globalMinDates.length > 2"> +{{ series.globalMinDates.length - 2 }}</span>
      </div>
    </UiCard>

    <!-- 90d low -->
    <UiCard v-if="next90dMin" padding="sm">
      <UiSectionHeader as="h4" class="mb-1">Low (next 90d)</UiSectionHeader>
      <div class="font-bold tabular" :class="next90dMin.value < 0 ? 'text-negative' : 'text-fg'">
        {{ next90dMin.value.toFixed(1) }}k
      </div>
      <div class="mt-0.5 text-fg-muted">{{ formatDate(next90dMin.date) }}</div>
    </UiCard>

    <!-- Next outflow -->
    <UiCard v-if="nextOutflow" padding="sm">
      <UiSectionHeader as="h4" class="mb-1">Next Outflow</UiSectionHeader>
      <div class="font-bold tabular text-negative">{{ nextOutflow.amount_k.toFixed(1) }}k</div>
      <div class="mt-0.5 break-words text-fg-muted line-clamp-2">{{ nextOutflow.description }}</div>
      <div class="text-fg-muted">{{ formatDate(nextOutflow.effective_date) }}</div>
    </UiCard>

    <!-- Next inflow -->
    <UiCard v-if="nextInflow" padding="sm">
      <UiSectionHeader as="h4" class="mb-1">Next Inflow</UiSectionHeader>
      <div class="font-bold tabular text-positive">+{{ nextInflow.amount_k.toFixed(1) }}k</div>
      <div class="mt-0.5 break-words text-fg-muted line-clamp-2">{{ nextInflow.description }}</div>
      <div class="text-fg-muted">{{ formatDate(nextInflow.effective_date) }}</div>
    </UiCard>

    <!-- Reserve -->
    <UiCard padding="sm">
      <UiSectionHeader as="h4" class="mb-1">Reserve Threshold</UiSectionHeader>
      <div class="font-bold tabular text-fg">{{ settings.reserve_k.toFixed(1) }}k</div>
    </UiCard>

    <!-- Recurring series -->
    <UiCard
      v-if="activeRecurringRules.length > 0"
      padding="sm"
      class="sm:col-span-2 lg:col-span-1"
    >
      <UiSectionHeader as="h4" class="mb-2">
        <i class="pi pi-refresh mr-1.5 text-[10px] text-primary" aria-hidden="true"></i>
        Recurring
        <template #actions>
          <div class="text-[10px] tabular text-fg-muted">{{ activeRecurringRules.length }}</div>
        </template>
      </UiSectionHeader>
      <div class="space-y-1.5">
        <div
          v-for="rule in activeRecurringRules"
          :key="rule.id"
          :data-testid="`sidebar.recurring.${rule.id}`"
          class="group rounded-ctl border border-line bg-surface-muted px-2 py-1.5"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0 break-words text-[11px] text-fg line-clamp-2" :title="rule.description">
              {{ rule.description }}
            </div>
            <div
              class="shrink-0 text-[11px] font-bold tabular"
              :class="rule.amount_k > 0 ? 'text-positive' : 'text-negative'"
            >
              {{ rule.amount_k > 0 ? '+' : '' }}{{ rule.amount_k.toFixed(1) }}k
            </div>
          </div>
          <div class="mt-0.5 flex items-center justify-between gap-2">
            <div class="min-w-0 truncate text-[9px] text-fg-muted">
              {{ describeRecurrence(rule) }} · {{ endLabel(rule) }}
            </div>
            <div class="flex shrink-0 gap-2 opacity-0 transition-opacity duration-fast ease-standard focus-within:opacity-100 group-hover:opacity-100 touch:opacity-100">
              <UiIconButton
                :data-testid="`sidebar.recurring.${rule.id}.edit`"
                title="Edit series"
                label="Edit series"
                @click="emit('editRecurring', rule.id)"
              >
                <i class="pi pi-pencil text-[9px]" aria-hidden="true"></i>
              </UiIconButton>
              <UiIconButton
                :data-testid="`sidebar.recurring.${rule.id}.delete`"
                variant="danger"
                title="Delete series"
                label="Delete series"
                @click="emit('deleteRecurring', rule.id)"
              >
                <i class="pi pi-trash text-[9px]" aria-hidden="true"></i>
              </UiIconButton>
            </div>
          </div>
        </div>
      </div>
    </UiCard>
  </div>
</template>
