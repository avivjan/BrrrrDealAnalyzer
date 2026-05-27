import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { liquidityApi } from '../api/liquidity'
import type {
  LiquidityTransaction,
  LiquidityTransactionCreate,
  LiquidityTransactionUpdate,
  LiquidityRecurringTransaction,
  LiquidityRecurringTransactionCreate,
  LiquidityRecurringTransactionUpdate,
  LiquiditySettings,
  LiquiditySettingsUpdate,
  LiquiditySeries,
  MercuryBalanceResponse,
} from '../types/liquidity'
import {
  buildDailyLiquiditySeries,
  computeDefaultRange,
  expandAllRecurringRules,
  simulateImpact,
  requiresSimulation,
  todayISO,
} from '../utils/liquidityEngine'
import type { SimulationResult } from '../types/liquidity'

export const useLiquidityStore = defineStore('liquidity', () => {
  const transactions = ref<LiquidityTransaction[]>([])
  const recurringRules = ref<LiquidityRecurringTransaction[]>([])
  const settings = ref<LiquiditySettings>({
    opening_balance_k: 0,
    opening_balance_date: todayISO(),
    reserve_k: 5,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)
  const _version = ref(0)

  const mercuryBalance = ref<MercuryBalanceResponse | null>(null)
  const mercurySyncing = ref(false)
  const mercuryError = ref<string | null>(null)
  const mercuryLastSyncedAt = ref<string | null>(null)

  // Effective transaction list = real one-off transactions + every virtual
  // instance projected from a recurring rule across the visible window.
  // The list is reused for the chart series and for simulation candidates
  // so both stay perfectly aligned.
  const effectiveTransactions = computed<LiquidityTransaction[]>(() => {
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

  const series = computed<LiquiditySeries>(() => {
    void _version.value
    const { rangeStart, rangeEnd } = computeDefaultRange(
      transactions.value,
      settings.value.opening_balance_date,
    )
    return buildDailyLiquiditySeries(
      effectiveTransactions.value,
      settings.value.opening_balance_k,
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
      settings.value.opening_balance_k,
      settings.value.opening_balance_date,
      rangeStart,
      rangeEnd,
      settings.value.reserve_k,
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
    const base = [...effectiveTransactions.value]
    if (action === 'add') {
      return [...base, txn]
    } else if (action === 'edit') {
      return base.map(t => t.id === oldTxnId ? txn : t)
    } else {
      return base.filter(t => t.id !== txn.id)
    }
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
    return [
      ...base,
      ...expandAllRecurringRules(rulesAfter, rangeStart, rangeEnd),
    ]
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
   * Fetch the live sum of Mercury account balances across every configured
   * workspace and re-anchor the liquidity timeline's opening balance to today.
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
        settings.value.opening_balance_k !== balance.total_balance_k ||
        settings.value.opening_balance_date !== today
      if (needsUpdate) {
        await updateSettings({
          opening_balance_k: balance.total_balance_k,
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
    addRecurring,
    updateRecurring,
    deleteRecurring,
    findRecurringRule,
    updateSettings,
    syncFromMercury,
    requiresSimulation,
  }
})
