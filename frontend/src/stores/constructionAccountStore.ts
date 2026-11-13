/**
 * The Construction Accounts page (tasks/todo/ConstructionAccountPerRehab.md). Every edit goes through `edit`:
 * preview it (the server saves nothing), and if it moves the liquidity timeline, ask with the prompt; on Confirm save
 * it, then replace the deal's status with the server's answer and reload the views that show the same data. An edit
 * that moves no timeline row saves directly, with a short "Saved" notice.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { constructionAccountApi } from '../api/constructionAccount'
import type {
  ConstructionAccountLinkReq, ConstructionAccountManualAdjustmentReq, ConstructionAccountRehabFiguresReq, ConstructionAccountStatus,
  ConstructionAccountSwitchReq, ConstructionAccountTotals, ConstructionAccountTransaction, ConstructionAccountTransactionOverrideReq,
  ConstructionAccountWriteOptions, ConstructionAccountWriteResult, MercuryConnectionStatus,
} from '../types/constructionAccount'
import type { UseDealValueForField } from '../types/liquidity'
import { todayISO } from '../utils/liquidityEngine'
import { formatMoney } from '../utils/money'
import { useBoughtDealStore } from './boughtDealStore'
import { useLiquidityStore } from './liquidityStore'
import {
  changedRowCountOf, useLiquidityTimelineChangePromptStore, type LiquidityTimelineChangePreview, type LiquidityTimelineFigureChange,
} from './liquidityTimelineChangePromptStore'

type Write = (options: ConstructionAccountWriteOptions) => Promise<ConstructionAccountWriteResult>

/** The figures a prompt lists when they move: label, and how to read it from a status. */
const FIGURES_SHOWN_IN_THE_PROMPT: { label: string; read: (status: ConstructionAccountStatus) => string }[] = [
  { label: 'Construction account', read: status => status.construction_account?.name ?? 'Not linked' },
  { label: 'Rehab cost', read: status => formatMoney(status.rehab_cost_dollars) },
  { label: 'Construction budget', read: status => formatMoney(status.construction_budget_dollars) },
  { label: 'Rehab cushion', read: status => formatMoney(status.rehab_cushion_dollars) },
  { label: 'Total to deposit', read: status => formatMoney(status.total_to_deposit_dollars) },
  { label: 'Loan draws pulled', read: status => formatMoney(status.loan_draws_pulled?.total_dollars) },
  { label: 'Rehab paid', read: status => formatMoney(status.rehab_payments_made?.total_dollars) },
  { label: 'Remaining deposit', read: status => formatMoney(status.remaining_deposit_dollars) },
  { label: 'Projected return at rehab end', read: status => formatMoney(status.projected_return_at_rehab_end_dollars) },
  { label: 'Safe to steal now', read: status => formatMoney(status.safe_to_steal_now_dollars) },
  { label: 'Top-up needed', read: status => formatMoney(status.top_up_needed_dollars) },
  { label: 'Buffer to keep in the account', read: status => formatMoney(status.minimum_balance_to_keep_in_construction_account_dollars) },
]

export function figureChangesBetween(before: ConstructionAccountStatus, after: ConstructionAccountStatus): LiquidityTimelineFigureChange[] {
  return FIGURES_SHOWN_IN_THE_PROMPT
    .map(figure => ({ label: figure.label, before: figure.read(before), after: figure.read(after) }))
    .filter(figure => figure.before !== figure.after)
}

export function previewOf(result: ConstructionAccountWriteResult): LiquidityTimelineChangePreview {
  return {
    rowChanges: result.liquidity_row_changes,
    figureChanges: figureChangesBetween(result.status_before, result.status_after),
    rowDescriptionsMarkedDone: result.row_descriptions_marked_done,
  }
}

export const useConstructionAccountStore = defineStore('constructionAccounts', () => {
  const accounts = ref<ConstructionAccountStatus[]>([])
  const totals = ref<ConstructionAccountTotals | null>(null)
  const isLoading = ref(false)
  const hasLoaded = ref(false)
  const loadErrorMessage = ref<string | null>(null)
  const transactionsByDealId = ref<Record<string, ConstructionAccountTransaction[]>>({})
  const connectionStatus = ref<MercuryConnectionStatus | null>(null)
  const nextMercuryReadNotBefore = ref<string | null>(null)

  const accountById = computed(() => new Map(accounts.value.map(status => [status.bought_deal_id, status])))

  async function load(): Promise<void> {
    isLoading.value = true
    loadErrorMessage.value = null
    try {
      const list = await constructionAccountApi.list()
      accounts.value = list.accounts
      totals.value = list.totals
      hasLoaded.value = true
    } catch {
      loadErrorMessage.value = 'The construction accounts could not be loaded.'
    } finally {
      isLoading.value = false
    }
  }

  async function loadConnectionStatus(): Promise<void> {
    connectionStatus.value = await constructionAccountApi.connectionStatus()
  }

  async function loadTransactions(boughtDealId: string): Promise<void> {
    transactionsByDealId.value = { ...transactionsByDealId.value, [boughtDealId]: await constructionAccountApi.transactions(boughtDealId) }
  }

  /** The views that show the same data: the timeline's rows (when loaded) and, after a rehab figure, the Bought board. */
  async function reloadWhatShowsTheSameData(boughtDealId: string, rehabFiguresChanged: boolean): Promise<void> {
    const liquidityStore = useLiquidityStore()
    const reloads: Promise<unknown>[] = [load()]
    if (liquidityStore.transactions.length || liquidityStore.importedDeals.length) reloads.push(liquidityStore.reloadTransactionsAndImportedDeals())
    const boughtDealStore = useBoughtDealStore()
    if (rehabFiguresChanged && boughtDealStore.boughtDeals.length) reloads.push(boughtDealStore.fetchBoughtDeals())
    if (transactionsByDealId.value[boughtDealId]) reloads.push(loadTransactions(boughtDealId))
    await Promise.all(reloads)
  }

  /**
   * Preview, ask if it moves the timeline, then save. Resolves true once saved, false when cancelled. A failed
   * preview throws (nothing was saved), so the caller can show why.
   */
  async function edit(boughtDealId: string, title: string, write: Write, options: { rehabFiguresChanged?: boolean } = {}): Promise<boolean> {
    const today = todayISO()
    const firstPreview = await write({ previewOnly: true, today })
    const promptStore = useLiquidityTimelineChangePromptStore()
    if (!firstPreview.changes_the_liquidity_timeline) {
      await write({ today })
      promptStore.showSaved()
      await reloadWhatShowsTheSameData(boughtDealId, !!options.rehabFiguresChanged)
      return true
    }
    let previewAlreadyRead: ConstructionAccountWriteResult | null = firstPreview
    return promptStore.ask({
      dealKey: `bought:${boughtDealId}`,
      title,
      loadPreview: async (useTheNewValueFor: UseDealValueForField[]) => {
        const preview = previewAlreadyRead && !useTheNewValueFor.length ? previewAlreadyRead : await write({ previewOnly: true, today, useTheNewValueFor })
        previewAlreadyRead = null
        return previewOf(preview)
      },
      confirm: async (useTheNewValueFor: UseDealValueForField[]) => {
        const saved = await write({ today, useTheNewValueFor })
        await reloadWhatShowsTheSameData(boughtDealId, !!options.rehabFiguresChanged)
        return changedRowCountOf(previewOf(saved))
      },
    })
  }

  // --- The edits, by what they change ---

  const saveRehabFigures = (boughtDealId: string, data: ConstructionAccountRehabFiguresReq, title = 'Change the rehab figures') =>
    edit(boughtDealId, title, options => constructionAccountApi.saveRehabFigures(boughtDealId, data, options), { rehabFiguresChanged: true })
  const saveLink = (boughtDealId: string, data: ConstructionAccountLinkReq, title = 'Save the construction account') =>
    edit(boughtDealId, title, options => constructionAccountApi.saveLink(boughtDealId, data, options))
  const unlink = (boughtDealId: string) =>
    edit(boughtDealId, 'Unlink the construction account', options => constructionAccountApi.unlink(boughtDealId, options))
  const switchAccount = (boughtDealId: string, data: ConstructionAccountSwitchReq) =>
    edit(boughtDealId, 'Switch the construction account', options => constructionAccountApi.switchAccount(boughtDealId, data, options))
  const addManualAdjustment = (boughtDealId: string, data: ConstructionAccountManualAdjustmentReq) =>
    edit(boughtDealId, data.adjustment_type === 'manual_payment' ? 'Add a payment made outside the account' : 'Add a draw received outside the account',
      options => constructionAccountApi.addManualAdjustment(boughtDealId, data, options))
  const updateManualAdjustment = (boughtDealId: string, adjustmentId: string, data: ConstructionAccountManualAdjustmentReq) =>
    edit(boughtDealId, 'Change a manual entry', options => constructionAccountApi.updateManualAdjustment(boughtDealId, adjustmentId, data, options))
  const deleteManualAdjustment = (boughtDealId: string, adjustmentId: string) =>
    edit(boughtDealId, 'Delete a manual entry', options => constructionAccountApi.deleteManualAdjustment(boughtDealId, adjustmentId, options))
  const setTransactionOverride = (boughtDealId: string, mercuryTransactionId: string, data: ConstructionAccountTransactionOverrideReq) =>
    edit(boughtDealId, data.ignored ? 'Ignore a bank transaction' : 'Change how a bank transaction counts',
      options => constructionAccountApi.setTransactionOverride(boughtDealId, mercuryTransactionId, data, options))
  const clearTransactionOverride = (boughtDealId: string, mercuryTransactionId: string) =>
    edit(boughtDealId, 'Put a bank transaction back on its automatic category',
      options => constructionAccountApi.clearTransactionOverride(boughtDealId, mercuryTransactionId, options))
  const markReadyForCloseOut = (boughtDealId: string) =>
    edit(boughtDealId, 'Mark ready for close-out', options => constructionAccountApi.markReadyForCloseOut(boughtDealId, options))
  const markClosedOut = (boughtDealId: string) =>
    edit(boughtDealId, 'Close the construction account out', options => constructionAccountApi.markClosedOut(boughtDealId, options))
  const reopen = (boughtDealId: string) =>
    edit(boughtDealId, 'Reopen the construction account', options => constructionAccountApi.reopen(boughtDealId, options))

  return {
    accounts, totals, isLoading, hasLoaded, loadErrorMessage, transactionsByDealId, connectionStatus, nextMercuryReadNotBefore, accountById,
    load, loadConnectionStatus, loadTransactions, edit,
    saveRehabFigures, saveLink, unlink, switchAccount, addManualAdjustment, updateManualAdjustment, deleteManualAdjustment,
    setTransactionOverride, clearTransactionOverride, markReadyForCloseOut, markClosedOut, reopen,
  }
})
