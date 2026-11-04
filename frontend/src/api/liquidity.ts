import { apiClient } from './index'
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
  MercuryBalanceResponse,
  DealCashRowChanges,
  DealMilestoneChangeReq,
  ImportedLiquidityDeal,
  LiquidityDealBoard,
  RemoveOpenDealRowsRes,
  UseDealValueForField,
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

  async markTransactionDone(id: string): Promise<LiquidityTransaction> {
    const res = await apiClient.post<LiquidityTransaction>(`/liquidity/transactions/${id}/done`)
    return res.data
  },

  async markTransactionNotDone(id: string): Promise<LiquidityTransaction> {
    const res = await apiClient.post<LiquidityTransaction>(`/liquidity/transactions/${id}/not-done`)
    return res.data
  },

  async applyBulkTransactionAction(data: LiquidityTransactionBulkActionReq): Promise<LiquidityTransaction[]> {
    const res = await apiClient.post<LiquidityTransaction[]>('/liquidity/transactions/bulk', data)
    return res.data
  },

  async getRecurring(): Promise<LiquidityRecurringTransaction[]> {
    const res = await apiClient.get<LiquidityRecurringTransaction[]>('/liquidity/recurring')
    return res.data
  },

  async createRecurring(
    data: LiquidityRecurringTransactionCreate,
  ): Promise<LiquidityRecurringTransaction> {
    const res = await apiClient.post<LiquidityRecurringTransaction>('/liquidity/recurring', data)
    return res.data
  },

  async updateRecurring(
    id: string,
    data: LiquidityRecurringTransactionUpdate,
  ): Promise<LiquidityRecurringTransaction> {
    const res = await apiClient.put<LiquidityRecurringTransaction>(`/liquidity/recurring/${id}`, data)
    return res.data
  },

  async deleteRecurring(id: string): Promise<void> {
    await apiClient.delete(`/liquidity/recurring/${id}`)
  },

  /** One occurrence of a recurring rule, by the date the rule gives it: done, open again, or moved. */
  async markRecurringOccurrenceDone(ruleId: string, scheduledDate: string): Promise<LiquidityRecurringTransaction> {
    const res = await apiClient.post<LiquidityRecurringTransaction>(
      `/liquidity/recurring/${encodeURIComponent(ruleId)}/occurrences/${encodeURIComponent(scheduledDate)}/done`)
    return res.data
  },

  async markRecurringOccurrenceNotDone(ruleId: string, scheduledDate: string): Promise<LiquidityRecurringTransaction> {
    const res = await apiClient.post<LiquidityRecurringTransaction>(
      `/liquidity/recurring/${encodeURIComponent(ruleId)}/occurrences/${encodeURIComponent(scheduledDate)}/not-done`)
    return res.data
  },

  async moveRecurringOccurrence(ruleId: string, scheduledDate: string, newEffectiveDate: string): Promise<LiquidityRecurringTransaction> {
    const res = await apiClient.post<LiquidityRecurringTransaction>(
      `/liquidity/recurring/${encodeURIComponent(ruleId)}/occurrences/${encodeURIComponent(scheduledDate)}/move`,
      { new_effective_date: newEffectiveDate })
    return res.data
  },

  async getSettings(): Promise<LiquiditySettings> {
    const res = await apiClient.get<LiquiditySettings>('/liquidity/settings')
    return res.data
  },

  async updateSettings(data: LiquiditySettingsUpdate): Promise<LiquiditySettings> {
    const res = await apiClient.put<LiquiditySettings>('/liquidity/settings', data)
    return res.data
  },

  async getMercuryBalance(): Promise<MercuryBalanceResponse> {
    const res = await apiClient.get<MercuryBalanceResponse>('/liquidity/mercury-balance')
    return res.data
  },

  // --- A BRRRR deal's Cash Needed rows in the timeline ---

  async getImportedDeals(today: string): Promise<ImportedLiquidityDeal[]> {
    const res = await apiClient.get<ImportedLiquidityDeal[]>('/liquidity/deals', { params: { today } })
    return res.data
  },

  async refreshLateRefis(today: string): Promise<{ added_row_count: number }> {
    const res = await apiClient.post<{ added_row_count: number }>('/liquidity/deals/refresh-late-refis', { today })
    return res.data
  },

  async previewDealImport(dealBoard: LiquidityDealBoard, dealId: string, today: string,
    useDealValueFor: UseDealValueForField[] = []): Promise<DealCashRowChanges> {
    const res = await apiClient.post<DealCashRowChanges>(`/liquidity/deals/${dealBoard}/${dealId}/import-preview`,
      { today, use_deal_value_for: useDealValueFor })
    return res.data
  },

  async importDeal(dealBoard: LiquidityDealBoard, dealId: string, today: string,
    useDealValueFor: UseDealValueForField[] = []): Promise<DealCashRowChanges> {
    const res = await apiClient.post<DealCashRowChanges>(`/liquidity/deals/${dealBoard}/${dealId}/import`,
      { today, use_deal_value_for: useDealValueFor })
    return res.data
  },

  async previewMilestoneChange(dealBoard: LiquidityDealBoard, dealId: string, data: DealMilestoneChangeReq): Promise<DealCashRowChanges> {
    const res = await apiClient.post<DealCashRowChanges>(`/liquidity/deals/${dealBoard}/${dealId}/milestones/preview`, data)
    return res.data
  },

  async applyMilestoneChange(dealBoard: LiquidityDealBoard, dealId: string, data: DealMilestoneChangeReq): Promise<DealCashRowChanges> {
    const res = await apiClient.post<DealCashRowChanges>(`/liquidity/deals/${dealBoard}/${dealId}/milestones/apply`, data)
    return res.data
  },

  async removeOpenDealRows(dealBoard: LiquidityDealBoard, dealId: string,
    earnestMoneyRefundDate: string | null): Promise<RemoveOpenDealRowsRes> {
    const res = await apiClient.post<RemoveOpenDealRowsRes>(`/liquidity/deals/${dealBoard}/${dealId}/remove-open-rows`,
      { earnest_money_refund_date: earnestMoneyRefundDate })
    return res.data
  },
}
