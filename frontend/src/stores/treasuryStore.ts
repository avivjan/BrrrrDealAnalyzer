import { defineStore } from 'pinia'
import { ref } from 'vue'
import { treasuryApi } from '../api/treasury'
import type {
  LLCConfiguration,
  LLCConfigurationCreate,
  LLCConfigurationUpdate,
  PropertyStatus,
  PropertyStatusCreate,
  PropertyStatusUpdate,
  TransactionLedger,
  TransactionLedgerCreate,
  TransactionLedgerUpdate,
  PropertyCashFlowHistory,
  PropertyCashFlowHistoryCreate,
  PropertyCashFlowHistoryUpdate,
} from '../types/treasury'

export const useTreasuryStore = defineStore('treasury', () => {
  const llcs = ref<LLCConfiguration[]>([])
  const properties = ref<PropertyStatus[]>([])
  const transactions = ref<TransactionLedger[]>([])
  const cashFlowHistory = ref<PropertyCashFlowHistory[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      const [llcRows, propRows, txnRows, histRows] = await Promise.all([
        treasuryApi.getLlcs(),
        treasuryApi.getProperties(),
        treasuryApi.getTransactions(),
        treasuryApi.getCashFlowHistory(),
      ])
      llcs.value = llcRows
      properties.value = propRows
      transactions.value = txnRows
      cashFlowHistory.value = histRows
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load treasury data'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createLlc(data: LLCConfigurationCreate) {
    const row = await treasuryApi.createLlc(data)
    llcs.value = [...llcs.value, row]
    return row
  }

  async function patchLlc(id: string, data: LLCConfigurationUpdate) {
    const row = await treasuryApi.updateLlc(id, data)
    llcs.value = llcs.value.map((item) => (item.llc_id === id ? row : item))
    return row
  }

  async function removeLlc(id: string) {
    await treasuryApi.deleteLlc(id)
    llcs.value = llcs.value.filter((item) => item.llc_id !== id)
    properties.value = properties.value.filter((item) => item.llc_id !== id)
  }

  async function createProperty(data: PropertyStatusCreate) {
    const row = await treasuryApi.createProperty(data)
    properties.value = [...properties.value, row]
    return row
  }

  async function patchProperty(id: string, data: PropertyStatusUpdate) {
    const row = await treasuryApi.updateProperty(id, data)
    properties.value = properties.value.map((item) => (item.property_id === id ? row : item))
    return row
  }

  async function removeProperty(id: string) {
    await treasuryApi.deleteProperty(id)
    properties.value = properties.value.filter((item) => item.property_id !== id)
    cashFlowHistory.value = cashFlowHistory.value.filter((item) => item.property_id !== id)
  }

  /**
   * Every transaction create/patch/delete can mutate one or two properties'
   * bucket balances server-side in real time (ingestion effects, manual
   * HITL reassignment, veil-protected transfers). Re-pull the property
   * list after each mutation so cards reflect the recalculation instantly
   * instead of going stale until the next full page load.
   */
  async function refreshProperties() {
    properties.value = await treasuryApi.getProperties()
  }

  async function createTransaction(data: TransactionLedgerCreate) {
    const row = await treasuryApi.createTransaction(data)
    transactions.value = [row, ...transactions.value]
    await refreshProperties()
    return row
  }

  async function patchTransaction(id: string, data: TransactionLedgerUpdate) {
    const row = await treasuryApi.updateTransaction(id, data)
    transactions.value = transactions.value.map((item) =>
      item.transaction_id === id ? row : item,
    )
    await refreshProperties()
    return row
  }

  async function removeTransaction(id: string) {
    await treasuryApi.deleteTransaction(id)
    transactions.value = transactions.value.filter((item) => item.transaction_id !== id)
    await refreshProperties()
  }

  async function createCashFlow(data: PropertyCashFlowHistoryCreate) {
    const row = await treasuryApi.createCashFlowHistory(data)
    cashFlowHistory.value = [...cashFlowHistory.value, row].sort((a, b) =>
      a.month_year.localeCompare(b.month_year),
    )
    return row
  }

  async function patchCashFlow(id: string, data: PropertyCashFlowHistoryUpdate) {
    const row = await treasuryApi.updateCashFlowHistory(id, data)
    cashFlowHistory.value = cashFlowHistory.value
      .map((item) => (item.history_id === id ? row : item))
      .sort((a, b) => a.month_year.localeCompare(b.month_year))
    return row
  }

  async function removeCashFlow(id: string) {
    await treasuryApi.deleteCashFlowHistory(id)
    cashFlowHistory.value = cashFlowHistory.value.filter((item) => item.history_id !== id)
  }

  return {
    llcs,
    properties,
    transactions,
    cashFlowHistory,
    loading,
    error,
    fetchAll,
    refreshProperties,
    createLlc,
    patchLlc,
    removeLlc,
    createProperty,
    patchProperty,
    removeProperty,
    createTransaction,
    patchTransaction,
    removeTransaction,
    createCashFlow,
    patchCashFlow,
    removeCashFlow,
  }
})
