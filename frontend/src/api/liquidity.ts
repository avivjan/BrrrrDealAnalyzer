import { apiClient } from './index'
import type {
  LiquidityTransaction,
  LiquidityTransactionCreate,
  LiquidityTransactionUpdate,
  LiquiditySettings,
  LiquiditySettingsUpdate,
} from '../types/liquidity'

export const liquidityApi = {
  async getTransactions(): Promise<LiquidityTransaction[]> {
    const res = await apiClient.get<LiquidityTransaction[]>('/liquidity/transactions')
    return res.data
  },

  async createTransaction(data: LiquidityTransactionCreate): Promise<LiquidityTransaction> {
    const res = await apiClient.post<LiquidityTransaction>('/liquidity/transactions', data)
    return res.data
  },

  async updateTransaction(id: string, data: LiquidityTransactionUpdate): Promise<LiquidityTransaction> {
    const res = await apiClient.put<LiquidityTransaction>(`/liquidity/transactions/${id}`, data)
    return res.data
  },

  async deleteTransaction(id: string): Promise<void> {
    await apiClient.delete(`/liquidity/transactions/${id}`)
  },

  async getSettings(): Promise<LiquiditySettings> {
    const res = await apiClient.get<LiquiditySettings>('/liquidity/settings')
    return res.data
  },

  async updateSettings(data: LiquiditySettingsUpdate): Promise<LiquiditySettings> {
    const res = await apiClient.put<LiquiditySettings>('/liquidity/settings', data)
    return res.data
  },
}
