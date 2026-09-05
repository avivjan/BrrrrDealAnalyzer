<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useLiquidityStore } from '../stores/liquidityStore'
import type {
  LiquidityTransaction,
  LiquidityRecurringTransaction,
  LiquidityRecurringFrequency,
  SimulationResult,
} from '../types/liquidity'
import { requiresSimulation } from '../utils/liquidityEngine'
import TimelineChart from '../components/liquidity/TimelineChart.vue'
import LiquiditySidebar from '../components/liquidity/LiquiditySidebar.vue'
import DayDetail from '../components/liquidity/DayDetail.vue'
import TransactionForm from '../components/liquidity/TransactionForm.vue'
import SimulationWarning from '../components/liquidity/SimulationWarning.vue'
import SettingsPanel from '../components/liquidity/SettingsPanel.vue'

const router = useRouter()
const store = useLiquidityStore()

// Save payloads emitted by TransactionForm. Mirrors the discriminated
// union over there; duplicated locally so we can name it in template refs
// and keep view <-> form coupling explicit.
type OneOffSavePayload = {
  kind: 'transaction'
  id?: string
  effective_date: string
  description: string
  amount_k: number
}

type RecurringSavePayload = {
  kind: 'recurring'
  id?: string
  description: string
  amount_k: number
  start_date: string
  end_date: string | null
  occurrences: number | null
  frequency: LiquidityRecurringFrequency
  interval: number
}

type SavePayload = OneOffSavePayload | RecurringSavePayload

const chartRef = ref<InstanceType<typeof TimelineChart> | null>(null)
const selectedDate = ref<string | null>(null)
const formOpen = ref(false)
const editingTxn = ref<LiquidityTransaction | null>(null)
const editingRecurring = ref<LiquidityRecurringTransaction | null>(null)
const prefillDate = ref<string | null>(null)
const settingsOpen = ref(false)

const warningOpen = ref(false)
const warningSeverity = ref<'hard' | 'soft' | 'none'>('none')
const warningResult = ref<SimulationResult | null>(null)
const pendingSave = ref<SavePayload | null>(null)

const toastMessage = ref('')
const toastVisible = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | undefined

const selectedBucket = computed(() => {
  if (!selectedDate.value) return null
  return store.series.days.find(d => d.date === selectedDate.value) ?? null
})

const hasData = computed(() =>
  store.transactions.length > 0 ||
  store.recurringRules.length > 0 ||
  store.settings.opening_balance_k !== 0 ||
  !!store.mercuryBalance
)

onMounted(async () => {
  await store.fetchAll()
  await store.syncFromMercury()
  if (store.mercuryError) {
    showToast('Mercury sync failed: ' + store.mercuryError)
  }
})

async function refreshFromMercury() {
  await store.syncFromMercury()
  if (store.mercuryError) {
    showToast('Mercury sync failed: ' + store.mercuryError)
  } else if (store.mercuryBalance) {
    const sum = store.mercuryBalance.total_balance_k
    const n = store.mercuryBalance.account_count
    showToast(`Synced from Mercury: ${sum.toFixed(1)}k across ${n} account${n === 1 ? '' : 's'}.`)
  }
}

function onSelectDay(date: string) {
  selectedDate.value = date
}

function openAddForm(date?: string) {
  editingTxn.value = null
  editingRecurring.value = null
  prefillDate.value = date ?? selectedDate.value
  formOpen.value = true
}

function openEditForm(txnId: string) {
  // Editing a virtual recurring instance jumps straight to its source rule;
  // the form switches into recurring mode automatically based on the
  // `editRecurring` prop.
  const virtual = store.effectiveTransactions.find(t => t.id === txnId)
  if (virtual?.recurring_rule_id) {
    const rule = store.findRecurringRule(virtual.recurring_rule_id)
    if (rule) {
      editingTxn.value = null
      editingRecurring.value = rule
      prefillDate.value = null
      formOpen.value = true
    }
    return
  }
  const txn = store.transactions.find(t => t.id === txnId)
  if (txn) {
    editingTxn.value = txn
    editingRecurring.value = null
    prefillDate.value = null
    formOpen.value = true
  }
}

async function onFormSave(data: SavePayload) {
  formOpen.value = false

  if (data.kind === 'recurring') {
    await handleRecurringSave(data)
    return
  }

  const needsSim = data.id
    ? requiresSimulation(store.transactions.find(t => t.id === data.id)!, data.amount_k, data.effective_date)
    : requiresSimulation(null, data.amount_k, data.effective_date)

  if (needsSim) {
    const fakeTxn: LiquidityTransaction = {
      id: data.id || '__candidate__',
      effective_date: data.effective_date,
      description: data.description,
      amount_k: data.amount_k,
    }
    const action = data.id ? 'edit' : 'add'
    const candidateList = store.buildCandidateList(action, fakeTxn, data.id)
    const result = store.runSimulation(candidateList)

    if (result.negativeDates.length > 0) {
      warningSeverity.value = 'hard'
      warningResult.value = result
      pendingSave.value = data
      warningOpen.value = true
      return
    }

    if (result.breachesReserve) {
      warningSeverity.value = 'soft'
      warningResult.value = result
      pendingSave.value = data
      warningOpen.value = true
      return
    }

    await doSave(data)
    showToast(`Saved. Window min: ${result.min.toFixed(1)}k on ${result.minDates[0]}`)
    return
  }

  await doSave(data)
  showToast('Transaction saved.')
}

/**
 * Recurring save path. Outflow series (or edits that worsen one) get the
 * same negative/reserve check as one-offs, but candidate generation has to
 * project the new rule across the timeline first or simulation only sees
 * occurrence #1.
 */
async function handleRecurringSave(data: RecurringSavePayload) {
  const candidateRule: LiquidityRecurringTransaction = {
    id: data.id || '__candidate__',
    description: data.description,
    amount_k: data.amount_k,
    start_date: data.start_date,
    end_date: data.end_date,
    occurrences: data.occurrences,
    frequency: data.frequency,
    interval: data.interval,
  }

  // Always simulate outflows — a recurring outflow can sink the timeline
  // far in the future even if amount-per-occurrence is small.
  const needsSim = data.amount_k < 0 || !!data.id
  if (needsSim) {
    const action: 'add' | 'edit' = data.id ? 'edit' : 'add'
    const candidateList = store.buildRecurringCandidateList(action, candidateRule, data.id)
    const result = store.runSimulation(candidateList)

    if (result.negativeDates.length > 0) {
      warningSeverity.value = 'hard'
      warningResult.value = result
      pendingSave.value = data
      warningOpen.value = true
      return
    }
    if (result.breachesReserve) {
      warningSeverity.value = 'soft'
      warningResult.value = result
      pendingSave.value = data
      warningOpen.value = true
      return
    }

    await doSaveRecurring(data)
    showToast(`Series saved. Window min: ${result.min.toFixed(1)}k on ${result.minDates[0]}`)
    return
  }

  await doSaveRecurring(data)
  showToast('Recurring series saved.')
}

async function onWarningConfirm() {
  warningOpen.value = false
  if (!pendingSave.value) return
  const payload = pendingSave.value
  pendingSave.value = null
  if (payload.kind === 'recurring') {
    await doSaveRecurring(payload)
  } else {
    await doSave(payload)
  }
}

function onWarningCancel() {
  warningOpen.value = false
  pendingSave.value = null
}

async function doSave(data: OneOffSavePayload) {
  try {
    if (data.id) {
      await store.updateTransaction(data.id, {
        effective_date: data.effective_date,
        description: data.description,
        amount_k: data.amount_k,
      })
    } else {
      await store.addTransaction({
        effective_date: data.effective_date,
        description: data.description,
        amount_k: data.amount_k,
      })
    }
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

async function doSaveRecurring(data: RecurringSavePayload) {
  try {
    if (data.id) {
      await store.updateRecurring(data.id, {
        description: data.description,
        amount_k: data.amount_k,
        start_date: data.start_date,
        end_date: data.end_date,
        occurrences: data.occurrences,
        frequency: data.frequency,
        interval: data.interval,
      })
    } else {
      await store.addRecurring({
        description: data.description,
        amount_k: data.amount_k,
        start_date: data.start_date,
        end_date: data.end_date,
        occurrences: data.occurrences,
        frequency: data.frequency,
        interval: data.interval,
      })
    }
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

function openEditRecurring(ruleId: string) {
  const rule = store.findRecurringRule(ruleId)
  if (!rule) return
  editingTxn.value = null
  editingRecurring.value = rule
  prefillDate.value = null
  formOpen.value = true
}

async function onDeleteRecurringRule(ruleId: string) {
  const rule = store.findRecurringRule(ruleId)
  if (!rule) return
  const ok = window.confirm(
    `Delete the entire recurring series "${rule.description}"? ` +
    `This removes every projected occurrence from the timeline.`,
  )
  if (!ok) return
  try {
    await store.deleteRecurring(ruleId)
    showToast('Recurring series deleted.')
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

async function onDeleteTxn(txnId: string) {
  // Virtual recurring instances delete the source rule (and so the whole
  // series). Confirm with the user first — a click-through deletion would
  // be too destructive here.
  const virtual = store.effectiveTransactions.find(t => t.id === txnId)
  if (virtual?.recurring_rule_id) {
    const rule = store.findRecurringRule(virtual.recurring_rule_id)
    if (!rule) return
    const ok = window.confirm(
      `Delete the entire recurring series "${rule.description}"? ` +
      `This removes every projected occurrence from the timeline.`,
    )
    if (!ok) return
    try {
      await store.deleteRecurring(rule.id)
      showToast('Recurring series deleted.')
    } catch (e: any) {
      showToast('Error: ' + (e?.response?.data?.detail || e.message))
    }
    return
  }

  try {
    await store.deleteTransaction(txnId)
    showToast('Transaction deleted.')
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

async function onSettingsSave(data: { opening_balance_k: number; opening_balance_date: string; reserve_k: number }) {
  settingsOpen.value = false
  try {
    await store.updateSettings(data)
    showToast('Settings saved.')
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

function showToast(msg: string) {
  toastMessage.value = msg
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 4000)
}
</script>

<template>
  <div class="flex min-h-dvh flex-col bg-page text-fg">
    <!-- Header -->
    <header
      class="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-line bg-surface px-3 py-2 sm:px-4 sm:py-3 md:bg-surface/90 md:backdrop-blur-sm"
    >
      <div class="flex min-w-0 items-center gap-2">
        <UiIconButton
          data-testid="liquidity.back"
          class="-ml-1"
          title="Back"
          label="Back"
          @click="router.push('/')"
        >
          <i class="pi pi-arrow-left text-sm" aria-hidden="true"></i>
        </UiIconButton>
        <h1 class="truncate text-base font-semibold tracking-tight text-fg">
          <i class="pi pi-chart-line mr-2 text-primary" aria-hidden="true"></i>
          Liquidity Timeline
        </h1>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <UiButton
          data-testid="liquidity.today"
          variant="ghost"
          size="sm"
          class="min-h-9 touch:min-h-11 gap-1.5"
          @click="chartRef?.centerOnToday()"
        >
          <i class="pi pi-crosshair text-[10px]" aria-hidden="true"></i> Today
        </UiButton>
        <UiButton
          data-testid="liquidity.mercury-sync"
          variant="ghost"
          size="sm"
          class="min-h-9 touch:min-h-11 gap-1.5"
          :disabled="store.mercurySyncing"
          :title="store.mercuryError ? 'Mercury error: ' + store.mercuryError : 'Re-sync opening balance from Mercury'"
          @click="refreshFromMercury"
        >
          <i :class="store.mercurySyncing ? 'pi pi-spin pi-spinner' : 'pi pi-sync'" class="text-[10px]" aria-hidden="true"></i>
          {{ store.mercurySyncing ? 'Syncing…' : 'Mercury' }}
        </UiButton>
        <UiButton
          data-testid="liquidity.settings-open"
          variant="ghost"
          size="sm"
          class="min-h-9 touch:min-h-11 gap-1.5"
          @click="settingsOpen = true"
        >
          <i class="pi pi-cog text-[10px]" aria-hidden="true"></i> Settings
        </UiButton>
        <UiButton
          data-testid="liquidity.add-flow"
          variant="primary"
          size="sm"
          class="min-h-9 touch:min-h-11 gap-1.5"
          @click="openAddForm()"
        >
          <i class="pi pi-plus text-[10px]" aria-hidden="true"></i> Add Flow
        </UiButton>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="store.loading" data-testid="liquidity.loading" class="flex flex-1 items-center justify-center p-6">
      <div class="text-center">
        <i class="pi pi-spin pi-spinner mb-3 text-2xl text-primary" aria-hidden="true"></i>
        <p class="text-sm text-fg-muted">Loading liquidity data...</p>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="store.error" data-testid="liquidity.error" class="flex flex-1 items-center justify-center p-6">
      <div class="max-w-sm text-center">
        <i class="pi pi-exclamation-circle mb-3 text-3xl text-negative" aria-hidden="true"></i>
        <p class="mb-2 text-sm font-semibold text-negative">Failed to load</p>
        <p class="mb-4 break-words text-xs text-fg-muted">{{ store.error }}</p>
        <UiButton
          data-testid="liquidity.retry"
          variant="secondary"
          size="sm"
          class="min-h-9 touch:min-h-11"
          @click="store.fetchAll()"
        >
          Retry
        </UiButton>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!hasData && !store.loading" data-testid="liquidity.empty" class="flex flex-1 items-center justify-center p-6">
      <UiEmptyState icon="pi pi-chart-line" class="max-w-md">
        No liquidity data yet
        <template #description>
          Set your opening balance and add your first cash flow to get started.
        </template>
        <template #actions>
          <div class="flex flex-wrap justify-center gap-3">
            <UiButton
              data-testid="liquidity.empty.settings"
              variant="secondary"
              @click="settingsOpen = true"
            >
              Set Opening Balance
            </UiButton>
            <UiButton
              data-testid="liquidity.empty.add"
              variant="primary"
              @click="openAddForm()"
            >
              Add First Flow
            </UiButton>
          </div>
        </template>
      </UiEmptyState>
    </div>

    <!-- Main content -->
    <div v-else class="flex min-h-0 flex-1 flex-col lg:flex-row">
      <!-- Chart area -->
      <div class="flex min-w-0 flex-1 flex-col">
        <!--
          `grid`, not a plain block: below `lg` the sidebar takes the column's
          leftover space, so this box is sized by its `min-h` alone and a
          `height: 100%` child would collapse to nothing against an indefinite
          parent. A single stretched grid row gives the chart its box either
          way. No size, padding or transform transition here or on any
          ancestor: the chart redraws from a ResizeObserver, so an animated box
          would repaint the canvas on every frame of it.
        -->
        <div class="grid min-h-[320px] flex-1 lg:min-h-[300px]">
          <TimelineChart
            ref="chartRef"
            :days="store.series.days"
            :global-min="store.series.globalMin"
            :global-min-dates="store.series.globalMinDates"
            :first-negative-date="store.series.firstNegativeDate"
            @select-day="onSelectDay"
          />
        </div>

        <!-- Bottom detail panel -->
        <div class="max-h-[260px] overflow-y-auto overscroll-contain border-t border-line bg-page p-3">
          <DayDetail
            v-if="selectedBucket"
            :bucket="selectedBucket"
            @edit-txn="openEditForm"
            @delete-txn="onDeleteTxn"
            @add-on-date="openAddForm"
          />
          <div v-else class="py-4 text-center text-xs text-fg-muted">
            Click or arrow-key to a day to see details
          </div>
        </div>
      </div>

      <!--
        Below `lg` the sidebar stacks under the chart instead of disappearing:
        the column direction of the parent is the only thing that moves it.
      -->
      <aside
        class="w-full shrink-0 border-t border-line bg-page p-3 lg:w-56 lg:overflow-y-auto lg:border-l lg:border-t-0"
      >
        <LiquiditySidebar
          :series="store.series"
          :settings="store.settings"
          :transactions="store.transactions"
          :recurring-rules="store.recurringRules"
          :mercury-balance="store.mercuryBalance"
          :mercury-syncing="store.mercurySyncing"
          :mercury-error="store.mercuryError"
          :mercury-last-synced-at="store.mercuryLastSyncedAt"
          @edit-recurring="openEditRecurring"
          @delete-recurring="onDeleteRecurringRule"
        />
      </aside>
    </div>

    <!-- Modals -->
    <TransactionForm
      :open="formOpen"
      :edit-txn="editingTxn"
      :edit-recurring="editingRecurring"
      :prefill-date="prefillDate"
      @close="formOpen = false"
      @save="onFormSave"
    />

    <SimulationWarning
      :open="warningOpen"
      :result="warningResult"
      :severity="warningSeverity"
      @confirm="onWarningConfirm"
      @cancel="onWarningCancel"
    />

    <SettingsPanel
      :open="settingsOpen"
      :settings="store.settings"
      @close="settingsOpen = false"
      @save="onSettingsSave"
    />

    <!-- Toast -->
    <Transition name="toast">
      <div
        v-if="toastVisible"
        data-testid="liquidity.toast"
        class="fixed inset-x-0 bottom-[max(1.5rem,env(safe-area-inset-bottom))] z-50 mx-auto w-fit max-w-[min(28rem,calc(100%-2rem))] rounded-card border border-line bg-surface px-4 py-2.5 text-xs text-fg shadow-2"
      >
        {{ toastMessage }}
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/*
 * The toast is `position: fixed`, so it is centred with auto margins rather
 * than a permanent `translateX(-50%)`; only the entry and exit move it.
 */
.toast-enter-active, .toast-leave-active {
  transition:
    opacity var(--dur-base) var(--ease-standard),
    transform var(--dur-base) var(--ease-standard);
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
