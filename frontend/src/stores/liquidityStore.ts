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
      const [txns, recurring, s] = await Promise.all([
        liquidityApi.getTransactions(),
        liquidityApi.getRecurring(),
        liquidityApi.getSettings(),
      ])
      transactions.value = txns
      recurringRules.value = recurring
      settings.value = s
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

  /** Done: the money moved (or the hold was released), so the row leaves the timeline. */
  async function markTransactionDone(id: string): Promise<void> {
    await liquidityApi.markTransactionDone(id)
    transactions.value = await liquidityApi.getTransactions()
    _version.value++
  }

  /** Undo of Done: the row is open again. */
  async function markTransactionNotDone(id: string): Promise<void> {
    await liquidityApi.markTransactionNotDone(id)
    transactions.value = await liquidityApi.getTransactions()
    _version.value++
  }

  async function applyBulkTransactionAction(data: LiquidityTransactionBulkActionReq): Promise<void> {
    await liquidityApi.applyBulkTransactionAction(data)
    transactions.value = await liquidityApi.getTransactions()
    _version.value++
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
    addRecurring,
    updateRecurring,
    deleteRecurring,
    findRecurringRule,
    updateSettings,
    syncFromMercury,
    requiresSimulation,
  }
})
