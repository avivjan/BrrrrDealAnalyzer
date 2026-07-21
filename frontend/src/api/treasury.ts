import { apiClient } from './index'
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

/** Encode a path segment so address-style IDs (spaces, commas) survive the URL. */
function pathSeg(id: string): string {
  return encodeURIComponent(id)
}

export const treasuryApi = {
  async getLlcs(): Promise<LLCConfiguration[]> {
    const res = await apiClient.get<LLCConfiguration[]>('/treasury/llcs')
    return res.data
  },

  async createLlc(data: LLCConfigurationCreate): Promise<LLCConfiguration> {
    const res = await apiClient.post<LLCConfiguration>('/treasury/llcs', data)
    return res.data
  },

  async updateLlc(id: string, data: LLCConfigurationUpdate): Promise<LLCConfiguration> {
    const res = await apiClient.put<LLCConfiguration>(`/treasury/llcs/${pathSeg(id)}`, data)
    return res.data
  },

  async deleteLlc(id: string): Promise<void> {
    await apiClient.delete(`/treasury/llcs/${pathSeg(id)}`)
  },

  async getProperties(llcId?: string): Promise<PropertyStatus[]> {
    const res = await apiClient.get<PropertyStatus[]>('/treasury/properties', {
      params: llcId ? { llc_id: llcId } : undefined,
    })
    return res.data
  },

  async createProperty(data: PropertyStatusCreate): Promise<PropertyStatus> {
    const res = await apiClient.post<PropertyStatus>('/treasury/properties', data)
    return res.data
  },

  async updateProperty(id: string, data: PropertyStatusUpdate): Promise<PropertyStatus> {
    // Query-param identity — path segments break on address-style IDs with commas/spaces.
    const res = await apiClient.put<PropertyStatus>('/treasury/properties/item', data, {
      params: { property_id: id },
    })
    return res.data
  },

  async deleteProperty(id: string): Promise<void> {
    await apiClient.delete('/treasury/properties/item', {
      params: { property_id: id },
    })
  },

  async getTransactions(propertyId?: string): Promise<TransactionLedger[]> {
    const res = await apiClient.get<TransactionLedger[]>('/treasury/transactions', {
      params: propertyId ? { property_id: propertyId } : undefined,
    })
    return res.data
  },

  async createTransaction(data: TransactionLedgerCreate): Promise<TransactionLedger> {
    const res = await apiClient.post<TransactionLedger>('/treasury/transactions', data)
    return res.data
  },

  async updateTransaction(id: string, data: TransactionLedgerUpdate): Promise<TransactionLedger> {
    const res = await apiClient.put<TransactionLedger>(
      `/treasury/transactions/${pathSeg(id)}`,
      data,
    )
    return res.data
  },

  async deleteTransaction(id: string): Promise<void> {
    await apiClient.delete(`/treasury/transactions/${pathSeg(id)}`)
  },

  async getCashFlowHistory(propertyId?: string): Promise<PropertyCashFlowHistory[]> {
    const res = await apiClient.get<PropertyCashFlowHistory[]>('/treasury/cash-flow-history', {
      params: propertyId ? { property_id: propertyId } : undefined,
    })
    return res.data
  },

  async createCashFlowHistory(
    data: PropertyCashFlowHistoryCreate,
  ): Promise<PropertyCashFlowHistory> {
    const res = await apiClient.post<PropertyCashFlowHistory>(
      '/treasury/cash-flow-history',
      data,
    )
    return res.data
  },

  async updateCashFlowHistory(
    id: string,
    data: PropertyCashFlowHistoryUpdate,
  ): Promise<PropertyCashFlowHistory> {
    const res = await apiClient.put<PropertyCashFlowHistory>(
      `/treasury/cash-flow-history/${pathSeg(id)}`,
      data,
    )
    return res.data
  },

  async deleteCashFlowHistory(id: string): Promise<void> {
    await apiClient.delete(`/treasury/cash-flow-history/${pathSeg(id)}`)
  },
}
