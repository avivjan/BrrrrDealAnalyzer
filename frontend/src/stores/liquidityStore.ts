import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { liquidityApi } from '../api/liquidity'
import type {
  LiquidityTransaction,
  LiquidityTransactionCreate,
  LiquidityTransactionUpdate,
  LiquidityTransactionBulkActionReq,
  LiquidityRecurringTransaction,
  LiquidityRecurringTransactionCreate,
  LiquidityRecurringTransactionUpdate,
  LiquiditySettings,
  LiquiditySettingsUpdate,
  LiquiditySeries,
  MercuryBalanceResponse,
  TransactionsAsOfToday,
  DealCashRowChange,
  DealCashRowChanges,
  DealMilestoneChangeReq,
  ImportedLiquidityDeal,
  LiquidityDealBoard,
  RemoveOpenDealRowsRes,
  UseDealValueForField,
} from '../types/liquidity'
import {
  buildDailyLiquiditySeries,
  computeDefaultRange,
  expandAllRecurringRules,
  projectTransactionsOntoToday,
  simulateImpact,
  requiresSimulation,
  todayISO,
} from '../utils/liquidityEngine'
import type { SimulationResult } from '../types/liquidity'
import { transactionsAfterDealChanges } from '../utils/dealCashRowsPreview'

export const useLiquidityStore = defineStore('liquidity', () => {
  const transactions = ref<LiquidityTransaction[]>([])
  const recurringRules = ref<LiquidityRecurringTransaction[]>([])
  const settings = ref<LiquiditySettings>({
    opening_balance_dollars: 0,
    opening_balance_date: todayISO(),
    reserve_dollars: 5000,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)
  const _version = ref(0)

  /** The BRRRR deals imported into the timeline (the Deals panel), with their milestones. */
  const importedDeals = ref<ImportedLiquidityDeal[]>([])

  const mercuryBalance = ref<MercuryBalanceResponse | null>(null)
  const mercurySyncing = ref(false)
  const mercuryError = ref<string | null>(null)
  const mercuryLastSyncedAt = ref<string | null>(null)

  // Every row in the visible window: the one-off transactions + every virtual
  // instance projected from a recurring rule.
  const transactionsInWindow = computed<LiquidityTransaction[]>(() => {
    void _version.value
    const { rangeStart, rangeEnd } = computeDefaultRange(
      transactions.value,
      settings.value.opening_balance_date,
    )
    const projected = expandAllRecurringRules(
      recurringRules.value,
      rangeStart,
      rangeEnd,
    )
    return [...transactions.value, ...projected]
  })

  // The rows as the timeline counts them today: done rows out, overdue money out on
  // today, overdue money in set aside (not counted). "Today" is the browser's local date.
  const transactionsAsOfToday = computed<TransactionsAsOfToday>(() =>
    projectTransactionsOntoToday(transactionsInWindow.value, todayISO()),
  )

  // Effective transaction list: what the balance counts. Reused for the chart series
  // and for simulation candidates so both stay perfectly aligned.
  const effectiveTransactions = computed<LiquidityTransaction[]>(() => transactionsAsOfToday.value.countedTransactions)
  const overdueMoneyOut = computed(() => transactionsAsOfToday.value.overdueMoneyOut)
  const expectedMoneyInNotCounted = computed(() => transactionsAsOfToday.value.expectedMoneyInNotCounted)

  const series = computed<LiquiditySeries>(() => {
    void _version.value
    const { rangeStart, rangeEnd } = computeDefaultRange(
      transactions.value,
      settings.value.opening_balance_date,
    )
    return buildDailyLiquiditySeries(
      effectiveTransactions.value,
      settings.value.opening_balance_dollars,
      settings.value.opening_balance_date,
      rangeStart,
      rangeEnd,
    )
  })

  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      // A late refi's carrying-cost months become real rows first, on the browser's local date.
      await liquidityApi.refreshLateRefis(todayISO()).catch(() => undefined)
      const [txns, recurring, s, deals] = await Promise.all([
        liquidityApi.getTransactions(),
        liquidityApi.getRecurring(),
        liquidityApi.getSettings(),
        liquidityApi.getImportedDeals(todayISO()).catch(() => [] as ImportedLiquidityDeal[]),
      ])
      transactions.value = txns
      recurringRules.value = recurring
      settings.value = s
      importedDeals.value = deals
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || 'Failed to load liquidity data'
    } finally {
      loading.value = false
    }
  }

  function runSimulation(
    candidateTxns: LiquidityTransaction[],
  ): SimulationResult {
    const { rangeStart, rangeEnd } = computeDefaultRange(
      candidateTxns,
      settings.value.opening_balance_date,
    )
    return simulateImpact(
      candidateTxns,
      settings.value.opening_balance_dollars,
      settings.value.opening_balance_date,
      rangeStart,
      rangeEnd,
      settings.value.reserve_dollars,
    )
  }

  /**
   * Build the candidate transaction list for simulation, including projected
   * recurring instances so the warning reflects the full picture.
   *
   * For add: baseline (one-offs + recurring projections) + new txn
   * For edit: baseline with old replaced by new
   * For delete: baseline with txn removed
   */
  function buildCandidateList(
    action: 'add' | 'edit' | 'delete',
    txn: LiquidityTransaction,
    oldTxnId?: string,
  ): LiquidityTransaction[] {
    const base = [...transactionsInWindow.value]
    const candidates = action === 'add'
      ? [...base, txn]
      : action === 'edit'
        ? base.map(t => t.id === oldTxnId ? { ...t, ...txn, id: t.id } : t)
        : base.filter(t => t.id !== txn.id)
    return projectTransactionsOntoToday(candidates, todayISO()).countedTransactions
  }

  /**
   * Build a simulation candidate list with one recurring rule swapped out
   * (or added/removed). The currently-projected occurrences of the affected
   * rule are stripped out before the new projection is added back so the
   * timeline doesn't double-count.
   */
  function buildRecurringCandidateList(
    action: 'add' | 'edit' | 'delete',
    rule: LiquidityRecurringTransaction,
    oldRuleId?: string,
  ): LiquidityTransaction[] {
    const base = [...transactions.value]
    const otherRules = recurringRules.value.filter(
      r => r.id !== (oldRuleId ?? rule.id),
    )
    const rulesAfter =
      action === 'delete'
        ? otherRules
        : action === 'edit'
          ? [...otherRules, rule]
          : [...recurringRules.value, rule]

    const { rangeStart, rangeEnd } = computeDefaultRange(
      base,
      settings.value.opening_balance_date,
    )
    return projectTransactionsOntoToday([
      ...base,
      ...expandAllRecurringRules(rulesAfter, rangeStart, rangeEnd),
    ], todayISO()).countedTransactions
  }

  async function addTransaction(data: LiquidityTransactionCreate): Promise<LiquidityTransaction> {
    const created = await liquidityApi.createTransaction(data)
    transactions.value = await liquidityApi.getTransactions()
    _version.value++
    return created
  }

  async function updateTransaction(id: string, data: LiquidityTransactionUpdate): Promise<LiquidityTransaction> {
    const updated = await liquidityApi.updateTransaction(id, data)
    transactions.value = await liquidityApi.getTransactions()
    _version.value++
    return updated
  }

  /**
   * After a Done or its undo: the rows again, and the imported deals too when a deal's row changed (their open /
   * done counts decide whether the legend lists the deal in the timeline or under Finished deals).
   */
  async function reloadAfterDoneChange(changedTransactionIds: string[]): Promise<void> {
    const aDealRowChanged = transactions.value.some(transaction => changedTransactionIds.includes(transaction.id) && !!transaction.source_deal_id)
    if (aDealRowChanged) {
      await reloadTransactionsAndImportedDeals()
      return
    }
    transactions.value = await liquidityApi.getTransactions()
    _version.value++
  }

  /** Done: the money moved (or the hold was released), so the row leaves the timeline. */
  async function markTransactionDone(id: string): Promise<void> {
    await liquidityApi.markTransactionDone(id)
    await reloadAfterDoneChange([id])
  }

  /** Undo of Done: the row is open again. */
  async function markTransactionNotDone(id: string): Promise<void> {
    await liquidityApi.markTransactionNotDone(id)
    await reloadAfterDoneChange([id])
  }

  async function applyBulkTransactionAction(data: LiquidityTransactionBulkActionReq): Promise<void> {
    await liquidityApi.applyBulkTransactionAction(data)
    if (data.recurring_occurrences?.length) recurringRules.value = await liquidityApi.getRecurring()
    await reloadAfterDoneChange(data.transaction_ids)
  }

  /** A recurring occurrence from its row id (`recurring:<rule>:<index>`): its rule and the date the rule gives it. */
  function recurringOccurrenceOf(transactionId: string): { ruleId: string; scheduledDate: string; effectiveDate: string } | null {
    if (!transactionId.startsWith('recurring:')) return null
    const occurrence = transactionsInWindow.value.find(transaction => transaction.id === transactionId)
    if (!occurrence?.recurring_rule_id || !occurrence.recurring_scheduled_date) return null
    return { ruleId: occurrence.recurring_rule_id, scheduledDate: occurrence.recurring_scheduled_date, effectiveDate: occurrence.effective_date }
  }

  /** The rule answers with its states: replace it in place, so the timeline re-expands it. */
  function replaceRecurringRule(rule: LiquidityRecurringTransaction): void {
    recurringRules.value = recurringRules.value.map(existing => (existing.id === rule.id ? rule : existing))
    _version.value++
  }

  async function markRecurringOccurrenceDone(ruleId: string, scheduledDate: string): Promise<void> {
    replaceRecurringRule(await liquidityApi.markRecurringOccurrenceDone(ruleId, scheduledDate))
  }

  async function markRecurringOccurrenceNotDone(ruleId: string, scheduledDate: string): Promise<void> {
    replaceRecurringRule(await liquidityApi.markRecurringOccurrenceNotDone(ruleId, scheduledDate))
  }

  async function moveRecurringOccurrence(ruleId: string, scheduledDate: string, newEffectiveDate: string): Promise<void> {
    replaceRecurringRule(await liquidityApi.moveRecurringOccurrence(ruleId, scheduledDate, newEffectiveDate))
  }

  async function reloadTransactionsAndImportedDeals(): Promise<void> {
    const [txns, deals] = await Promise.all([liquidityApi.getTransactions(), liquidityApi.getImportedDeals(todayISO())])
    transactions.value = txns
    importedDeals.value = deals
    _version.value++
  }

  async function fetchImportedDeals(): Promise<void> {
    importedDeals.value = await liquidityApi.getImportedDeals(todayISO())
  }

  /**
   * The balance today vs "with these changes" of a deal's rows, over one shared range (the chart's dashed line
   * and the preview's insights).
   */
  function seriesWithAndWithoutDealChanges(changes: DealCashRowChange[]): { seriesWithoutTheDeal: LiquiditySeries; seriesWithTheDeal: LiquiditySeries } {
    const today = todayISO()
    const oneOffTransactionsAfter = transactionsAfterDealChanges(transactions.value, changes)
    const { rangeStart, rangeEnd } = computeDefaultRange(
      [...transactions.value, ...oneOffTransactionsAfter],
      settings.value.opening_balance_date,
    )
    const recurringOccurrences = expandAllRecurringRules(recurringRules.value, rangeStart, rangeEnd)
    const seriesOf = (oneOffTransactions: LiquidityTransaction[]) => buildDailyLiquiditySeries(
      projectTransactionsOntoToday([...oneOffTransactions, ...recurringOccurrences], today).countedTransactions,
      settings.value.opening_balance_dollars,
      settings.value.opening_balance_date,
      rangeStart,
      rangeEnd,
    )
    return { seriesWithoutTheDeal: seriesOf(transactions.value), seriesWithTheDeal: seriesOf(oneOffTransactionsAfter) }
  }

  function previewDealImport(dealBoard: LiquidityDealBoard, dealId: string, useDealValueFor: UseDealValueForField[] = []): Promise<DealCashRowChanges> {
    return liquidityApi.previewDealImport(dealBoard, dealId, todayISO(), useDealValueFor)
  }

  /** Import the deal's rows, or re-sync them (the same call). */
  async function importDeal(dealBoard: LiquidityDealBoard, dealId: string, useDealValueFor: UseDealValueForField[] = []): Promise<DealCashRowChanges> {
    const result = await liquidityApi.importDeal(dealBoard, dealId, todayISO(), useDealValueFor)
    await reloadTransactionsAndImportedDeals()
    return result
  }

  function previewMilestoneChange(dealBoard: LiquidityDealBoard, dealId: string, change: DealMilestoneChangeReq): Promise<DealCashRowChanges> {
    return liquidityApi.previewMilestoneChange(dealBoard, dealId, { ...change, today: todayISO() })
  }

  /** Approve or move a milestone: the deal's dates change and its rows re-sync, as the preview listed. */
  async function applyMilestoneChange(dealBoard: LiquidityDealBoard, dealId: string, change: DealMilestoneChangeReq): Promise<DealCashRowChanges> {
    const result = await liquidityApi.applyMilestoneChange(dealBoard, dealId, { ...change, today: todayISO() })
    await reloadTransactionsAndImportedDeals()
    return result
  }

  /** A dead deal: its open rows go, and the earnest money may come back as money in on `earnestMoneyRefundDate`. */
  async function removeOpenDealRows(dealBoard: LiquidityDealBoard, dealId: string, earnestMoneyRefundDate: string | null): Promise<RemoveOpenDealRowsRes> {
    const result = await liquidityApi.removeOpenDealRows(dealBoard, dealId, earnestMoneyRefundDate)
    await reloadTransactionsAndImportedDeals()
    return result
  }

  async function deleteTransaction(id: string): Promise<void> {
    await liquidityApi.deleteTransaction(id)
    transactions.value = await liquidityApi.getTransactions()
    _version.value++
  }

  async function addRecurring(
    data: LiquidityRecurringTransactionCreate,
  ): Promise<LiquidityRecurringTransaction> {
    const created = await liquidityApi.createRecurring(data)
    recurringRules.value = await liquidityApi.getRecurring()
    _version.value++
    return created
  }

  async function updateRecurring(
    id: string,
    data: LiquidityRecurringTransactionUpdate,
  ): Promise<LiquidityRecurringTransaction> {
    const updated = await liquidityApi.updateRecurring(id, data)
    recurringRules.value = await liquidityApi.getRecurring()
    _version.value++
    return updated
  }

  async function deleteRecurring(id: string): Promise<void> {
    await liquidityApi.deleteRecurring(id)
    recurringRules.value = await liquidityApi.getRecurring()
    _version.value++
  }

  /** Resolve the source rule for a virtual recurring instance. */
  function findRecurringRule(ruleId: string): LiquidityRecurringTransaction | null {
    return recurringRules.value.find(r => r.id === ruleId) ?? null
  }

  async function updateSettings(data: LiquiditySettingsUpdate): Promise<void> {
    settings.value = await liquidityApi.updateSettings(data)
    _version.value++
  }

  /**
   * Fetch the live Mercury balances across every configured workspace and re-anchor the
   * liquidity timeline's opening balance to today on the accounts counted as cash (the
   * settings' choice; every active account until one is made).
   *
   * Only rebases when ALL workspaces succeeded — a partial sum would
   * understate true cash on hand and is unsafe to anchor against. On partial
   * failure the per-workspace errors are exposed via `mercuryBalance.workspace_errors`
   * and a summary is stored on `mercuryError`.
   */
  async function syncFromMercury(): Promise<void> {
    mercurySyncing.value = true
    mercuryError.value = null
    try {
      const balance = await liquidityApi.getMercuryBalance()
      mercuryBalance.value = balance
      mercuryLastSyncedAt.value = new Date().toISOString()

      if (balance.workspace_errors.length > 0) {
        mercuryError.value = balance.workspace_errors
          .map(w => `${w.workspace}: ${w.error}`)
          .join('; ')
        return
      }

      const today = todayISO()
      const needsUpdate =
        settings.value.opening_balance_dollars !== balance.counted_as_cash_balance_dollars ||
        settings.value.opening_balance_date !== today
      if (needsUpdate) {
        await updateSettings({
          opening_balance_dollars: balance.counted_as_cash_balance_dollars,
          opening_balance_date: today,
        })
      }
    } catch (e: any) {
      mercuryError.value =
        e?.response?.data?.detail || e?.message || 'Failed to sync from Mercury'
    } finally {
      mercurySyncing.value = false
    }
  }

  return {
    transactions,
    recurringRules,
    effectiveTransactions,
    overdueMoneyOut,
    expectedMoneyInNotCounted,
    settings,
    loading,
    error,
    series,
    importedDeals,
    fetchImportedDeals,
    seriesWithAndWithoutDealChanges,
    previewDealImport,
    importDeal,
    previewMilestoneChange,
    applyMilestoneChange,
    removeOpenDealRows,
    mercuryBalance,
    mercurySyncing,
    mercuryError,
    mercuryLastSyncedAt,
    fetchAll,
    runSimulation,
    buildCandidateList,
    buildRecurringCandidateList,
    addTransaction,
    updateTransaction,
    deleteTransaction,
    markTransactionDone,
    markTransactionNotDone,
    applyBulkTransactionAction,
    transactionsInWindow,
    recurringOccurrenceOf,
    markRecurringOccurrenceDone,
    markRecurringOccurrenceNotDone,
    moveRecurringOccurrence,
    addRecurring,
    updateRecurring,
    deleteRecurring,
    findRecurringRule,
    updateSettings,
    syncFromMercury,
    requiresSimulation,
  }
})
