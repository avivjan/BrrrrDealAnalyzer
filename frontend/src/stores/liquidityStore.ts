import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { liquidityApi } from '../api/liquidity'
import type {
  LiquidityTransaction,
  LiquidityTransactionCreate,
  LiquidityTransactionUpdate,
  LiquiditySettings,
  LiquiditySettingsUpdate,
  LiquiditySeries,
} from '../types/liquidity'
import {
  buildDailyLiquiditySeries,
  computeDefaultRange,
  simulateImpact,
  requiresSimulation,
  todayISO,
} from '../utils/liquidityEngine'
import type { SimulationResult } from '../types/liquidity'

export const useLiquidityStore = defineStore('liquidity', () => {
  const transactions = ref<LiquidityTransaction[]>([])
  const settings = ref<LiquiditySettings>({
    opening_balance_k: 0,
    opening_balance_date: todayISO(),
    reserve_k: 5,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)
  const _version = ref(0)

  const series = computed<LiquiditySeries>(() => {
    void _version.value
    const { rangeStart, rangeEnd } = computeDefaultRange(
      transactions.value,
      settings.value.opening_balance_date,
    )
    return buildDailyLiquiditySeries(
      transactions.value,
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
      const [txns, s] = await Promise.all([
        liquidityApi.getTransactions(),
        liquidityApi.getSettings(),
      ])
      transactions.value = txns
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
   * Build the candidate transaction list for simulation.
   * For add: baseline + new txn
   * For edit: baseline with old replaced by new
   * For delete: baseline with txn removed
   */
  function buildCandidateList(
    action: 'add' | 'edit' | 'delete',
    txn: LiquidityTransaction,
    oldTxnId?: string,
  ): LiquidityTransaction[] {
    const base = [...transactions.value]
    if (action === 'add') {
      return [...base, txn]
    } else if (action === 'edit') {
      return base.map(t => t.id === oldTxnId ? txn : t)
    } else {
      return base.filter(t => t.id !== txn.id)
    }
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

  async function updateSettings(data: LiquiditySettingsUpdate): Promise<void> {
    settings.value = await liquidityApi.updateSettings(data)
    _version.value++
  }

  return {
    transactions,
    settings,
    loading,
    error,
    series,
    fetchAll,
    runSimulation,
    buildCandidateList,
    addTransaction,
    updateTransaction,
    deleteTransaction,
    updateSettings,
    requiresSimulation,
  }
})
