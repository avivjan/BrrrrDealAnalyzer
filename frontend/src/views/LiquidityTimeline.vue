<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useLiquidityStore } from '../stores/liquidityStore'
import type {
  LiquidityTransaction,
  LiquidityRecurringTransaction,
  LiquidityRecurringFrequency,
  LiquiditySettingsUpdate,
  SimulationResult,
  DealCashRowChanges,
  DealMilestone,
  ImportedLiquidityDeal,
} from '../types/liquidity'
import { addDays, requiresSimulation, todayISO } from '../utils/liquidityEngine'
import { formatMoney } from '../utils/money'
import TimelineChart from '../components/liquidity/TimelineChart.vue'
import LiquiditySidebar from '../components/liquidity/LiquiditySidebar.vue'
import DayDetail from '../components/liquidity/DayDetail.vue'
import TransactionForm from '../components/liquidity/TransactionForm.vue'
import SimulationWarning from '../components/liquidity/SimulationWarning.vue'
import SettingsPanel from '../components/liquidity/SettingsPanel.vue'
import OverdueTransactionsStrip from '../components/liquidity/OverdueTransactionsStrip.vue'
import LiquidityDealsPanel from '../components/liquidity/LiquidityDealsPanel.vue'
import DealMilestoneChangeModal from '../components/liquidity/DealMilestoneChangeModal.vue'
import DealImportPreviewModal from '../components/liquidity/DealImportPreviewModal.vue'


const store = useLiquidityStore()

// Save payloads emitted by TransactionForm. Mirrors the discriminated
// union over there; duplicated locally so we can name it in template refs
// and keep view <-> form coupling explicit.
type OneOffSavePayload = {
  kind: 'transaction'
  id?: string
  effective_date: string
  description: string
  amount_dollars: number
}

type RecurringSavePayload = {
  kind: 'recurring'
  id?: string
  description: string
  amount_dollars: number
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

/** Narrow screens: the sidebar is an inline collapsible section instead of a right rail. */
const sidebarOpen = ref(false)

/** Header KPIs, from the series App already computed — no fetch. */
const todayIso = todayISO()
const kpis = computed(() => {
  const days = store.series.days
  const todayBucket = days.find(d => d.date === todayIso) ?? null
  const firstNeg = store.series.firstNegativeDate
  const daysToNegative = firstNeg
    ? Math.round((new Date(firstNeg + 'T00:00:00').getTime() - new Date(todayIso + 'T00:00:00').getTime()) / 86_400_000)
    : null
  const fmt = (v: number) => formatMoney(Math.round(v))
  return {
    balance: todayBucket ? fmt(todayBucket.balance_dollars) : '—',
    balanceTone: todayBucket && todayBucket.balance_dollars < 0 ? 'negative' : 'neutral',
    min: fmt(store.series.globalMin),
    minTone: store.series.globalMin < 0 ? 'negative' : store.series.globalMin < store.settings.reserve_dollars ? 'warning' : 'positive',
    minDate: store.series.globalMinDates[0] ?? null,
    daysToNegative: daysToNegative === null ? 'None' : daysToNegative <= 0 ? 'Now' : `${daysToNegative}d`,
    daysTone: daysToNegative === null ? 'positive' : daysToNegative <= 30 ? 'negative' : 'warning',
    reserve: fmt(store.settings.reserve_dollars),
  } as const
})

/** "HH:MM" of the last Mercury sync, for the balance KPI's status title. */
const mercurySyncedTime = computed(() => {
  if (!store.mercuryLastSyncedAt) return null
  const d = new Date(store.mercuryLastSyncedAt)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
})

const toastMessage = ref('')
const toastVisible = ref(false)
/** The toast's "Undo" for a quick row action (Done, a move, an amount); null = no Undo button. */
const toastUndo = ref<(() => Promise<void>) | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | undefined

const selectedBucket = computed(() => {
  if (!selectedDate.value) return null
  return store.series.days.find(d => d.date === selectedDate.value) ?? null
})

const hasData = computed(() =>
  store.transactions.length > 0 ||
  store.recurringRules.length > 0 ||
  store.settings.opening_balance_dollars !== 0 ||
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
    const sum = store.mercuryBalance.total_balance_dollars
    const n = store.mercuryBalance.account_count
    showToast(`Synced from Mercury: ${formatMoney(sum)} across ${n} account${n === 1 ? '' : 's'}.`)
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
    ? requiresSimulation(store.transactions.find(t => t.id === data.id)!, data.amount_dollars, data.effective_date)
    : requiresSimulation(null, data.amount_dollars, data.effective_date)

  if (needsSim) {
    const fakeTxn: LiquidityTransaction = {
      id: data.id || '__candidate__',
      effective_date: data.effective_date,
      description: data.description,
      amount_dollars: data.amount_dollars,
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
    showToast(`Saved. Window min: ${formatMoney(result.min)} on ${result.minDates[0]}`)
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
    amount_dollars: data.amount_dollars,
    start_date: data.start_date,
    end_date: data.end_date,
    occurrences: data.occurrences,
    frequency: data.frequency,
    interval: data.interval,
  }

  // Always simulate outflows — a recurring outflow can sink the timeline
  // far in the future even if amount-per-occurrence is small.
  const needsSim = data.amount_dollars < 0 || !!data.id
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
    showToast(`Series saved. Window min: ${formatMoney(result.min)} on ${result.minDates[0]}`)
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
        amount_dollars: data.amount_dollars,
      })
    } else {
      await store.addTransaction({
        effective_date: data.effective_date,
        description: data.description,
        amount_dollars: data.amount_dollars,
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
        amount_dollars: data.amount_dollars,
        start_date: data.start_date,
        end_date: data.end_date,
        occurrences: data.occurrences,
        frequency: data.frequency,
        interval: data.interval,
      })
    } else {
      await store.addRecurring({
        description: data.description,
        amount_dollars: data.amount_dollars,
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

async function onSettingsSave(data: LiquiditySettingsUpdate) {
  settingsOpen.value = false
  try {
    const countedAccountsChanged = data.mercury_account_ids_counted_as_cash !== undefined
      && JSON.stringify(data.mercury_account_ids_counted_as_cash) !== JSON.stringify(store.settings.mercury_account_ids_counted_as_cash ?? null)
    await store.updateSettings(data)
    // A new choice of accounts re-anchors today's balance on them.
    if (countedAccountsChanged) await store.syncFromMercury()
    showToast('Settings saved.')
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

// -- quick row actions: one tap each, an Undo on the toast ---------------------------------
function findOneOffTransaction(id: string) {
  return store.transactions.find(t => t.id === id) ?? null
}

async function runQuickAction(action: () => Promise<void>, message: string, undo: (() => Promise<void>) | null) {
  try {
    await action()
    showToast(message, undo)
  } catch (e: any) {
    showToast('Error: ' + (e?.response?.data?.detail || e.message))
  }
}

async function onMarkTransactionDone(id: string) {
  await runQuickAction(() => store.markTransactionDone(id), 'Marked done.', () => store.markTransactionNotDone(id))
}

async function onMoveTransactionToDate(id: string, newEffectiveDate: string) {
  const previousDate = findOneOffTransaction(id)?.effective_date
  await runQuickAction(
    async () => { await store.updateTransaction(id, { effective_date: newEffectiveDate }) },
    `Moved to ${newEffectiveDate}.`,
    previousDate ? async () => { await store.updateTransaction(id, { effective_date: previousDate }) } : null,
  )
}

async function onChangeTransactionAmount(id: string, newAmountDollars: number) {
  const previousAmount = findOneOffTransaction(id)?.amount_dollars
  await runQuickAction(
    async () => { await store.updateTransaction(id, { amount_dollars: newAmountDollars }) },
    `Amount changed to ${formatMoney(newAmountDollars)}.`,
    previousAmount !== undefined ? async () => { await store.updateTransaction(id, { amount_dollars: previousAmount }) } : null,
  )
}

async function onBulkMarkDone(ids: string[]) {
  await runQuickAction(
    () => store.applyBulkTransactionAction({ transaction_ids: ids, action: 'mark_done' }),
    `${ids.length} marked done.`,
    () => store.applyBulkTransactionAction({ transaction_ids: ids, action: 'mark_not_done' }),
  )
}

async function onBulkMoveToDate(ids: string[], newEffectiveDate: string) {
  await runQuickAction(
    () => store.applyBulkTransactionAction({ transaction_ids: ids, action: 'move_to_date', new_effective_date: newEffectiveDate }),
    `${ids.length} moved to ${newEffectiveDate}.`,
    null,
  )
}

async function onUndo() {
  const undo = toastUndo.value
  toastUndo.value = null
  toastVisible.value = false
  if (undo) await runQuickAction(undo, 'Undone.', null)
}

// --- Imported deals: milestones, re-sync after a deal edit, a dead deal ---
const milestoneChange = ref<{ deal: ImportedLiquidityDeal; milestone: DealMilestone; approve: boolean } | null>(null)
const dealToResync = ref<ImportedLiquidityDeal | null>(null)

function onChangeMilestone(deal: ImportedLiquidityDeal, milestone: DealMilestone, approve: boolean) {
  milestoneChange.value = { deal, milestone, approve }
}

function describeRowChanges(result: DealCashRowChanges): string {
  const counts = result.change_counts
  return `${counts.updated} changed, ${counts.added} added, ${counts.removed} removed.`
}

async function onRemoveOpenDealRows(deal: ImportedLiquidityDeal) {
  if (!window.confirm(`Remove the ${deal.open_row_count} open liquidity rows of ${deal.deal_address}? Done rows stay.`)) return
  const refundEarnestMoney = window.confirm('Add the earnest money deposit back as money in, a week from today?')
  try {
    const result = await store.removeOpenDealRows(deal.deal_board, deal.deal_id, refundEarnestMoney ? addDays(todayISO(), 7) : null)
    showToast(`Removed ${result.removed_row_count} rows${result.earnest_money_refund_transaction_id ? ', earnest money refund added' : ''}.`)
  } catch (e: any) {
    showToast(e?.response?.data?.detail || e?.message || 'Could not remove the rows')
  }
}

function showToast(msg: string, undo: (() => Promise<void>) | null = null) {
  toastMessage.value = msg
  toastUndo.value = undo
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 4000)
}
</script>

<template>
  <!--
    UI v3: a grid dashboard inside the shell (which owns the viewport, the
    sticky header and the h1). Hero header → four KPIs (Today's balance
    carries the Mercury status) → the chart → day detail + the Upcoming
    sidebar. Below `lg` the sidebar is an inline collapsible section rather
    than a hidden rail, so every figure is reachable on a phone. Every hook,
    handler, store call, modal and the 4 s toast are the v1 ones.

    No size, padding or transform transition on the chart panel or any of its
    ancestors: the chart re-measures itself from a ResizeObserver.
  -->
  <div class="mx-auto flex w-full max-w-[96rem] flex-col gap-4 px-3 py-4 text-fg sm:px-5 lg:px-6 lg:py-6">
    <!-- Header: the hero pattern every page shares (eyebrow, title, controls). -->
    <UiTransition preset="hero" appear>
      <header class="flex flex-wrap items-end gap-3">
        <div class="min-w-0 flex-1">
          <p data-hero="eyebrow" class="numeric text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
            Cash
          </p>
          <UiSectionHeader
            as="h2"
            data-hero="title"
            class="[&_[data-part=title]]:font-display [&_[data-part=title]]:text-2xl [&_[data-part=title]]:tracking-display"
          >
            Liquidity Timeline
          </UiSectionHeader>
        </div>

        <div data-hero="item" class="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <UiButton data-testid="liquidity.today" variant="secondary" size="sm" class="min-h-9 touch:min-h-11 gap-1.5" @click="chartRef?.centerOnToday()">
            <i class="pi pi-crosshair text-[10px]" aria-hidden="true"></i> Today
          </UiButton>
          <UiButton
            data-testid="liquidity.mercury-sync"
            variant="secondary"
            size="sm"
            class="min-h-9 touch:min-h-11 gap-1.5"
            :disabled="store.mercurySyncing"
            :title="store.mercuryError ? 'Mercury error: ' + store.mercuryError : 'Re-sync opening balance from Mercury'"
            @click="refreshFromMercury"
          >
            <i :class="store.mercurySyncing ? 'pi pi-spin pi-spinner' : 'pi pi-sync'" class="text-[10px]" aria-hidden="true"></i>
            {{ store.mercurySyncing ? 'Syncing…' : 'Mercury' }}
          </UiButton>
          <UiButton data-testid="liquidity.settings-open" variant="secondary" size="sm" class="min-h-9 touch:min-h-11 gap-1.5" @click="settingsOpen = true">
            <i class="pi pi-cog text-[10px]" aria-hidden="true"></i> Settings
          </UiButton>
          <UiButton data-testid="liquidity.add-flow" variant="primary" size="sm" class="min-h-9 touch:min-h-11 gap-1.5 shadow-glow-primary" @click="openAddForm()">
            <i class="pi pi-plus text-[10px]" aria-hidden="true"></i> Add Flow
          </UiButton>
        </div>
      </header>
    </UiTransition>

    <!-- Loading -->
    <div v-if="store.loading" data-testid="liquidity.loading" class="flex min-h-[40vh] items-center justify-center p-6">
      <div class="text-center">
        <i class="pi pi-spin pi-spinner mb-3 text-2xl text-primary" aria-hidden="true"></i>
        <p class="text-sm text-fg-muted">Loading liquidity data...</p>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="store.error" data-testid="liquidity.error" class="flex min-h-[40vh] items-center justify-center p-6">
      <UiSurface :level="1" padding="lg" class="max-w-sm text-center">
        <i class="pi pi-exclamation-circle mb-3 text-3xl text-negative" aria-hidden="true"></i>
        <p class="mb-2 text-sm font-semibold text-negative">Failed to load</p>
        <p class="mb-4 break-words text-xs text-fg-muted">{{ store.error }}</p>
        <UiButton data-testid="liquidity.retry" variant="secondary" size="sm" class="min-h-9 touch:min-h-11" @click="store.fetchAll()">
          Retry
        </UiButton>
      </UiSurface>
    </div>

    <!-- Empty state -->
    <div v-else-if="!hasData && !store.loading" data-testid="liquidity.empty" class="flex min-h-[40vh] items-center justify-center p-6">
      <UiEmptyState icon="pi pi-chart-line" class="max-w-md">
        No liquidity data yet
        <template #description>
          Set your opening balance and add your first cash flow to get started.
        </template>
        <template #actions>
          <div class="flex flex-wrap justify-center gap-3">
            <UiButton data-testid="liquidity.empty.settings" variant="secondary" @click="settingsOpen = true">
              Set Opening Balance
            </UiButton>
            <UiButton data-testid="liquidity.empty.add" variant="primary" @click="openAddForm()">
              Add First Flow
            </UiButton>
          </div>
        </template>
      </UiEmptyState>
    </div>

    <!-- Dashboard -->
    <template v-else>
      <div v-reveal.stagger class="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <!--
          Today's balance carries the Mercury status in its footer: the sync
          line and the per-workspace breakdown that used to be a sidebar card.
          The `sidebar.*` hooks on them are the e2e's and stay as they were.
        -->
        <UiKpiCard data-reveal data-testid="liquidity.kpi.balance" label="Today's balance" :tone="kpis.balanceTone" icon="pi pi-wallet">
          <template #value><span v-count-up>{{ kpis.balance }}</span></template>
          <template #footer>
            <div v-if="store.mercurySyncing" class="flex items-center gap-1 text-[10px] text-fg-muted">
              <i class="pi pi-spin pi-spinner text-[9px]" aria-hidden="true"></i> syncing
            </div>
            <div
              v-else-if="store.mercuryError"
              class="flex items-center gap-1 text-[10px] text-negative"
              :title="store.mercuryError"
            >
              <i class="pi pi-exclamation-triangle text-[9px]" aria-hidden="true"></i>
              {{ store.mercuryBalance && store.mercuryBalance.workspaces.length > 0 ? 'partial sync' : 'mercury offline' }}
            </div>
            <div
              v-else-if="store.mercuryBalance"
              class="flex items-center gap-1 text-[10px] text-positive"
              :title="`Synced ${store.mercuryBalance.account_count} account(s) across ${store.mercuryBalance.workspace_count} workspace(s)` + (mercurySyncedTime ? ' at ' + mercurySyncedTime : '')"
            >
              <i class="pi pi-check-circle text-[9px]" aria-hidden="true"></i>
              mercury · {{ store.mercuryBalance.workspace_count }}
            </div>

            <!-- Per-workspace breakdown -->
            <div
              v-if="store.mercuryBalance && store.mercuryBalance.workspaces.length > 0"
              class="mt-2 space-y-2 border-t border-line pt-2"
            >
              <div v-for="ws in store.mercuryBalance.workspaces" :key="ws.workspace" :data-testid="`sidebar.workspace.${ws.workspace}`" class="space-y-0.5">
                <div class="flex items-center justify-between gap-2 text-[10px]">
                  <span class="min-w-0 truncate font-semibold uppercase tracking-wide text-fg">{{ ws.workspace }}</span>
                  <span class="whitespace-nowrap numeric text-fg">{{ formatMoney(ws.total_balance_dollars) }}</span>
                </div>
                <div
                  v-for="a in ws.accounts"
                  :key="a.id"
                  :data-testid="`sidebar.account.${a.id}`"
                  class="flex items-center justify-between gap-2 pl-2 text-[10px] text-fg-muted"
                >
                  <span class="min-w-0 truncate pr-1">{{ a.name || a.type || 'Account' }}</span>
                  <span class="whitespace-nowrap numeric text-fg-muted">{{ formatMoney(a.current_balance_dollars) }}</span>
                </div>
              </div>
            </div>

            <!-- Per-workspace errors -->
            <div
              v-if="store.mercuryBalance && store.mercuryBalance.workspace_errors.length > 0"
              class="mt-2 space-y-0.5 border-t border-line pt-2"
            >
              <div
                v-for="err in store.mercuryBalance.workspace_errors"
                :key="err.workspace"
                :data-testid="`sidebar.workspace-error.${err.workspace}`"
                class="flex items-center justify-between gap-2 text-[10px] text-negative"
                :title="err.error"
              >
                <span class="font-semibold uppercase tracking-wide">{{ err.workspace }}</span>
                <span class="min-w-0 truncate pl-2">{{ err.error }}</span>
              </div>
            </div>
          </template>
        </UiKpiCard>
        <UiKpiCard data-reveal data-testid="liquidity.kpi.min" label="Window minimum" :tone="kpis.minTone" icon="pi pi-arrow-down" :delta="kpis.minDate ? `on ${kpis.minDate}` : undefined">
          <template #value><span v-count-up>{{ kpis.min }}</span></template>
        </UiKpiCard>
        <UiKpiCard data-reveal data-testid="liquidity.kpi.negative" label="Days to negative" :value="kpis.daysToNegative" :tone="kpis.daysTone" icon="pi pi-exclamation-triangle" />
        <UiKpiCard data-reveal data-testid="liquidity.kpi.reserve" label="Reserve floor" icon="pi pi-shield">
          <template #value><span v-count-up>{{ kpis.reserve }}</span></template>
        </UiKpiCard>
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_18rem] xl:grid-cols-[minmax(0,1fr)_20rem]">
        <!-- Overdue strip + chart + day detail -->
        <div class="flex min-w-0 flex-col gap-4">
          <OverdueTransactionsStrip
            :overdue-money-out="store.overdueMoneyOut"
            :expected-money-in-not-counted="store.expectedMoneyInNotCounted"
            @mark-done="onMarkTransactionDone"
            @move-to-date="onMoveTransactionToDate"
            @change-amount="onChangeTransactionAmount"
            @bulk-mark-done="onBulkMarkDone"
            @bulk-move-to-date="onBulkMoveToDate"
          />
          <LiquidityDealsPanel
            :imported-deals="store.importedDeals"
            :transactions="store.transactions"
            @change-milestone="onChangeMilestone"
            @review-changes="(deal) => (dealToResync = deal)"
            @remove-open-rows="onRemoveOpenDealRows"
          />
          <UiSurface :level="1" padding="none" class="overflow-hidden">
            <div class="grid h-[340px] min-h-[320px] sm:h-[380px]">
              <TimelineChart
                ref="chartRef"
                :days="store.series.days"
                :global-min="store.series.globalMin"
                :global-min-dates="store.series.globalMinDates"
                :first-negative-date="store.series.firstNegativeDate"
                :reserve-dollars="store.settings.reserve_dollars"
                @select-day="onSelectDay"
              />
            </div>
          </UiSurface>

          <div class="max-h-[320px] overflow-y-auto overscroll-contain">
            <DayDetail
              v-if="selectedBucket"
              :bucket="selectedBucket"
              @edit-txn="openEditForm"
              @delete-txn="onDeleteTxn"
              @add-on-date="openAddForm"
              @mark-done="onMarkTransactionDone"
              @move-to-date="onMoveTransactionToDate"
              @change-amount="onChangeTransactionAmount"
            />
            <UiSurface v-else :level="2" padding="md" class="text-center text-xs text-fg-muted">
              Click or arrow-key to a day to see details
            </UiSurface>
          </div>
        </div>

        <!-- Sidebar (Upcoming): right rail on lg+, inline collapsible below -->
        <aside aria-label="Upcoming" class="min-w-0">
          <UiButton
            data-testid="liquidity.sidebar-toggle"
            variant="secondary"
            block
            class="lg:hidden"
            :aria-expanded="sidebarOpen"
            aria-controls="liquidity-sidebar"
            @click="sidebarOpen = !sidebarOpen"
          >
            <i :class="sidebarOpen ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="text-xs" aria-hidden="true"></i>
            {{ sidebarOpen ? 'Hide overview' : 'Show overview' }}
          </UiButton>
          <div id="liquidity-sidebar" :class="sidebarOpen ? 'mt-3 block' : 'hidden lg:block'">
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
          </div>
        </aside>
      </div>
    </template>

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
      :mercury-accounts="store.mercuryBalance?.accounts ?? []"
      @close="settingsOpen = false"
      @save="onSettingsSave"
    />

    <DealMilestoneChangeModal
      v-if="milestoneChange"
      :deal="milestoneChange.deal"
      :milestone="milestoneChange.milestone"
      :approve="milestoneChange.approve"
      @close="milestoneChange = null"
      @applied="(result) => showToast(`Milestone saved: ${describeRowChanges(result)}`)"
    />

    <DealImportPreviewModal
      v-if="dealToResync"
      :deal-board="dealToResync.deal_board"
      :deal-id="dealToResync.deal_id"
      :deal-address="dealToResync.deal_address"
      @close="dealToResync = null"
      @imported="(result) => showToast(`Re-synced: ${describeRowChanges(result)}`)"
    />

    <!-- Toast -->
    <Transition name="toast">
      <div
        v-if="toastVisible"
        data-testid="liquidity.toast"
        class="fixed inset-x-0 bottom-[max(1.5rem,env(safe-area-inset-bottom))] z-50 mx-auto w-fit max-w-[min(28rem,calc(100%-2rem))] rounded-card border-ui border-line bg-surface px-4 py-2.5 text-xs text-fg shadow-3"
      >
        <span>{{ toastMessage }}</span>
        <button
          v-if="toastUndo"
          type="button"
          data-testid="liquidity.toast.undo"
          class="ml-3 font-semibold text-primary hover:text-primary-hover"
          @click="onUndo"
        >Undo</button>
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
