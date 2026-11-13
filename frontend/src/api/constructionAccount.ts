/**
 * /liquidity/construction-accounts/* (tasks/todo/ConstructionAccountPerRehab.md). Every write takes the same options:
 * `previewOnly` answers what it would change and saves nothing (the confirmation prompt), `today` is the browser's
 * date, and `useTheNewValueFor` names the rows you edited by hand that should take the new value anyway.
 */
import { apiClient } from './index'
import type {
  ConstructionAccountLinkReq, ConstructionAccountList, ConstructionAccountManualAdjustmentReq, ConstructionAccountRefreshResult,
  ConstructionAccountRehabFiguresReq, ConstructionAccountSwitchPreview, ConstructionAccountSwitchReq, ConstructionAccountTransaction,
  ConstructionAccountTransactionOverrideReq, ConstructionAccountWriteOptions, ConstructionAccountWriteResult, MercuryConnectionStatus,
  MercuryLastChange,
} from '../types/constructionAccount'

const BASE = '/liquidity/construction-accounts'

function writeParams(options: ConstructionAccountWriteOptions = {}): URLSearchParams {
  const params = new URLSearchParams()
  if (options.previewOnly) params.set('preview_only', 'true')
  if (options.today) params.set('today', options.today)
  for (const choice of options.useTheNewValueFor ?? []) params.append('use_the_new_value_for', `${choice.transaction_id}:${choice.field}`)
  return params
}

function dealUrl(boughtDealId: string, rest = ''): string {
  return `${BASE}/${encodeURIComponent(boughtDealId)}${rest}`
}

export const constructionAccountApi = {
  async list(): Promise<ConstructionAccountList> {
    return (await apiClient.get<ConstructionAccountList>(BASE)).data
  },

  async refresh(today: string, isABackgroundPoll = false): Promise<ConstructionAccountRefreshResult> {
    return (await apiClient.post<ConstructionAccountRefreshResult>(`${BASE}/refresh`, { today, is_a_background_poll: isABackgroundPoll })).data
  },

  async lastChange(): Promise<MercuryLastChange> {
    return (await apiClient.get<MercuryLastChange>(`${BASE}/last-change`)).data
  },

  async connectionStatus(): Promise<MercuryConnectionStatus> {
    return (await apiClient.get<MercuryConnectionStatus>('/liquidity/mercury-connection-status')).data
  },

  async transactions(boughtDealId: string): Promise<ConstructionAccountTransaction[]> {
    return (await apiClient.get<ConstructionAccountTransaction[]>(dealUrl(boughtDealId, '/transactions'))).data
  },

  async switchPreview(boughtDealId: string): Promise<ConstructionAccountSwitchPreview> {
    return (await apiClient.get<ConstructionAccountSwitchPreview>(dealUrl(boughtDealId, '/switch-account-preview'))).data
  },

  // --- Writes: each one previewable ---

  async saveRehabFigures(boughtDealId: string, data: ConstructionAccountRehabFiguresReq, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.put<ConstructionAccountWriteResult>(dealUrl(boughtDealId, '/rehab-figures'), data, { params: writeParams(options) })).data
  },

  async saveLink(boughtDealId: string, data: ConstructionAccountLinkReq, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.put<ConstructionAccountWriteResult>(dealUrl(boughtDealId), data, { params: writeParams(options) })).data
  },

  async unlink(boughtDealId: string, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.delete<ConstructionAccountWriteResult>(dealUrl(boughtDealId), { params: writeParams(options) })).data
  },

  async switchAccount(boughtDealId: string, data: ConstructionAccountSwitchReq, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.post<ConstructionAccountWriteResult>(dealUrl(boughtDealId, '/switch-account'), data, { params: writeParams(options) })).data
  },

  async addManualAdjustment(boughtDealId: string, data: ConstructionAccountManualAdjustmentReq, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.post<ConstructionAccountWriteResult>(dealUrl(boughtDealId, '/manual-adjustments'), data, { params: writeParams(options) })).data
  },

  async updateManualAdjustment(boughtDealId: string, adjustmentId: string, data: ConstructionAccountManualAdjustmentReq,
    options?: ConstructionAccountWriteOptions) {
    return (await apiClient.put<ConstructionAccountWriteResult>(dealUrl(boughtDealId, `/manual-adjustments/${encodeURIComponent(adjustmentId)}`), data,
      { params: writeParams(options) })).data
  },

  async deleteManualAdjustment(boughtDealId: string, adjustmentId: string, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.delete<ConstructionAccountWriteResult>(dealUrl(boughtDealId, `/manual-adjustments/${encodeURIComponent(adjustmentId)}`),
      { params: writeParams(options) })).data
  },

  async setTransactionOverride(boughtDealId: string, mercuryTransactionId: string, data: ConstructionAccountTransactionOverrideReq,
    options?: ConstructionAccountWriteOptions) {
    return (await apiClient.put<ConstructionAccountWriteResult>(
      dealUrl(boughtDealId, `/transactions/${encodeURIComponent(mercuryTransactionId)}/override`), data, { params: writeParams(options) })).data
  },

  async clearTransactionOverride(boughtDealId: string, mercuryTransactionId: string, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.delete<ConstructionAccountWriteResult>(
      dealUrl(boughtDealId, `/transactions/${encodeURIComponent(mercuryTransactionId)}/override`), { params: writeParams(options) })).data
  },

  async markReadyForCloseOut(boughtDealId: string, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.post<ConstructionAccountWriteResult>(dealUrl(boughtDealId, '/mark-ready-for-close-out'), null, { params: writeParams(options) })).data
  },

  async markClosedOut(boughtDealId: string, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.post<ConstructionAccountWriteResult>(dealUrl(boughtDealId, '/mark-closed-out'), null, { params: writeParams(options) })).data
  },

  async reopen(boughtDealId: string, options?: ConstructionAccountWriteOptions) {
    return (await apiClient.post<ConstructionAccountWriteResult>(dealUrl(boughtDealId, '/reopen'), null, { params: writeParams(options) })).data
  },
}
