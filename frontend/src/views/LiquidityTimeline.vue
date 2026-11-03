<script setup lang="ts">
import { ref, computed, onMounted, toRef } from 'vue'
import { useRouter } from 'vue-router'
import { useLiquidityStore } from '../stores/liquidityStore'
import { provideLiquidityDealAttribution } from '../composables/useLiquidityDealAttribution'
import { useOneTapMilestoneApproval } from '../composables/useOneTapMilestoneApproval'
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
import TransactionForm from '../components/liquidity/TransactionForm.vue'
import SimulationWarning from '../components/liquidity/SimulationWarning.vue'
import SettingsPanel from '../components/liquidity/SettingsPanel.vue'
import DealMilestoneChangeModal from '../components/liquidity/DealMilestoneChangeModal.vue'
import DealImportPreviewModal from '../components/liquidity/DealImportPreviewModal.vue'
import LiquidityTheaterMode from '../components/liquidity/theater/LiquidityTheaterMode.vue'


const store = useLiquidityStore()

/** Every row below can show the deal it came from, in that deal's color (done rows of a finished deal too). */
provideLiquidityDealAttribution(toRef(store, 'importedDeals'))

// --- The page is the theater (tasks/todo/LiquidityTheaterOnly.md): leaving it goes back, or to the Dashboard ---
const router = useRouter()
function leaveLiquidityPage() {
  // vue-router records the previous in-app page in history.state.back; a direct link has none.
  if (window.history.state?.back) router.back()
  else void router.push('/')
}

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

const formOpen = ref(false)
const editingTxn = ref<LiquidityTransaction | null>(null)
const editingRecurring = ref<LiquidityRecurringTransaction | null>(null)
const prefillDate = ref<string | null>(null)
const settingsOpen = ref(false)

const warningOpen = ref(false)
const warningSeverity = ref<'hard' | 'soft' | 'none'>('none')
const warningResult = ref<SimulationResult | null>(null)
const pendingSave = ref<SavePayload | null>(null)


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


const toastMessage = ref('')
const toastVisible = ref(false)
/** The toast's action ("Undo" after a quick row action, "Retry" after a failed load); null = no button. */
const toastUndo = ref<(() => Promise<void>) | null>(null)
const toastActionLabel = ref('Undo')
let toastTimer: ReturnType<typeof setTimeout> | undefined



async function loadLiquidityData() {
  await store.fetchAll()
  if (store.error) showToast('Failed to load: ' + store.error, loadLiquidityData, 'Retry')
}

onMounted(async () => {
  await loadLiquidityData()
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

function openAddForm(date?: string) {
  editingTxn.value = null
  editingRecurring.value = null
  prefillDate.value = date ?? null
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
  if (undo && toastActionLabel.value !== 'Undo') await undo()
  else if (undo) await runQuickAction(undo, 'Undone.', null)
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

/** Done on a milestone: approved in one tap when nothing else changes, otherwise its before -> after list opens. */
const { milestoneKeyBeingApproved, approveMilestoneOnItsPlannedDate } = useOneTapMilestoneApproval({
  previewMilestoneChange: (dealBoard, dealId, change) => store.previewMilestoneChange(dealBoard, dealId, change),
  applyMilestoneChange: (dealBoard, dealId, change) => store.applyMilestoneChange(dealBoard, dealId, change),
  openMilestoneApprovalReview: (deal, milestone) => onChangeMilestone(deal, milestone, true),
  showToast: (message) => showToast(message),
})

/** One of this view's own dialogs is open: theater mode leaves Esc and its shortcuts to it. */
const anotherLiquidityDialogIsOpen = computed(() =>
  formOpen.value || settingsOpen.value || warningOpen.value || !!milestoneChange.value || !!dealToResync.value)

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

function showToast(msg: string, undo: (() => Promise<void>) | null = null, actionLabel = 'Undo') {
  toastMessage.value = msg
  toastUndo.value = undo
  toastActionLabel.value = actionLabel
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 4000)
}
</script>

<template>
  <!--
    The liquidity page is the theater (tasks/todo/LiquidityTheaterOnly.md): the chart over the whole viewport,
    everything else in its overlays. This view keeps the handlers, the modals and the toast; Esc with nothing
    open, or ×, leaves the page.
  -->
  <div class="text-fg">
    <LiquidityTheaterMode
      :headline-figures="kpis"
      :is-another-dialog-open="anotherLiquidityDialogIsOpen"
      :milestone-key-being-approved="milestoneKeyBeingApproved"
      @leave="leaveLiquidityPage"
      @add-flow="(date) => openAddForm(date)"
      @edit-txn="openEditForm"
      @delete-txn="onDeleteTxn"
      @open-settings="settingsOpen = true"
      @sync-mercury="refreshFromMercury"
      @edit-recurring="openEditRecurring"
      @delete-recurring="onDeleteRecurringRule"
      @mark-done="onMarkTransactionDone"
      @move-to-date="onMoveTransactionToDate"
      @change-amount="onChangeTransactionAmount"
      @bulk-mark-done="onBulkMarkDone"
      @bulk-move-to-date="onBulkMoveToDate"
      @approve-milestone="approveMilestoneOnItsPlannedDate"
      @change-milestone="onChangeMilestone"
      @review-changes="(deal) => (dealToResync = deal)"
      @remove-deal-from-timeline="onRemoveOpenDealRows"
    />

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
        class="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-50 mx-auto w-fit max-w-[min(28rem,calc(100%-2rem))] rounded-card border-ui border-line bg-surface px-4 py-2.5 text-xs text-fg shadow-3"
      >
        <span>{{ toastMessage }}</span>
        <button
          v-if="toastUndo"
          type="button"
          data-testid="liquidity.toast.undo"
          class="ml-3 font-semibold text-primary hover:text-primary-hover"
          @click="onUndo"
        >{{ toastActionLabel }}</button>
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
