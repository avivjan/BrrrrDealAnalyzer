/**
 * A BRRRR deal's rows in the liquidity timeline, as the deal boards see them (tasks/todo/DealCashInLiquidity.md):
 * whether the deal is imported (directly, or through its Bought copy), and the prompts when the deal dies or is
 * deleted (its open rows go; the earnest money may come back as money in).
 *
 * A save that changes an imported deal's rows opens "This changes the liquidity timeline" at once
 * (tasks/todo/ConstructionAccountPerRehab.md, Requirement 1): the server only flags the deal, and Confirm re-syncs it.
 * Cancel leaves the rows as they are; the prompt comes back on the deal's next save and when Liquidity or Construction
 * Accounts opens.
 */
import { dealOnTheLiquidityTimeline } from '../navigation/appLinks'
import { useConstructionAccountStore } from '../stores/constructionAccountStore'
import { useLiquidityStore } from '../stores/liquidityStore'
import { changedRowCountOf, useLiquidityTimelineChangePromptStore } from '../stores/liquidityTimelineChangePromptStore'
import type { ImportedLiquidityDeal, LiquidityDealBoard, UseDealValueForField } from '../types/liquidity'
import { addDays, todayISO } from '../utils/liquidityEngine'

export const DEAD_DEAL_STAGE = 5

export function useDealLiquidityRows() {
  const liquidityStore = useLiquidityStore()

  function importedDeal(dealBoard: LiquidityDealBoard, dealId: string): ImportedLiquidityDeal | null {
    return liquidityStore.importedDeals.find(deal => deal.deal_board === dealBoard && deal.deal_id === dealId) ?? null
  }

  /** A My Deals deal moved to Bought: the Bought copy holds its rows, so this one cannot be imported again. */
  function boughtCopyInLiquidity(myDealsDealId: string): ImportedLiquidityDeal | null {
    return liquidityStore.importedDeals.find(deal => deal.my_deals_deal_id_it_was_moved_from === myDealsDealId) ?? null
  }

  async function refreshImportedDeals(): Promise<void> {
    await liquidityStore.fetchImportedDeals().catch(() => undefined)
  }

  /** The prompt for one deal: its preview is the re-sync preview, Confirm is the re-sync. Resolves true once synced. */
  function askToSyncDealRows(dealBoard: LiquidityDealBoard, dealId: string, dealAddress: string): Promise<boolean> {
    return useLiquidityTimelineChangePromptStore().ask({
      dealKey: `${dealBoard}:${dealId}`,
      title: `${dealAddress || 'This deal'} changed`,
      timelineLink: dealOnTheLiquidityTimeline(dealBoard, dealId),
      loadPreview: async (useTheNewValueFor: UseDealValueForField[]) => ({
        rowChanges: await liquidityStore.previewDealImport(dealBoard, dealId, useTheNewValueFor),
        figureChanges: [],
        rowDescriptionsMarkedDone: [],
      }),
      confirm: async (useTheNewValueFor: UseDealValueForField[]) => {
        const synced = await liquidityStore.importDeal(dealBoard, dealId, useTheNewValueFor)
        const constructionAccountStore = useConstructionAccountStore()
        if (constructionAccountStore.hasLoaded) await constructionAccountStore.load()
        return changedRowCountOf({ rowChanges: synced, figureChanges: [], rowDescriptionsMarkedDone: [] })
      },
    })
  }

  /** After a deal save landed: when the deal is imported and the save changed its rows, ask at once. */
  async function askToSyncDealRowsIfTheSaveChangedThem(dealBoard: LiquidityDealBoard, dealId: string, dealAddress: string): Promise<void> {
    if (!importedDeal(dealBoard, dealId)) return   // not in the timeline (the deal modal loads the list when it opens)
    await refreshImportedDeals()
    if (importedDeal(dealBoard, dealId)?.liquidity_rows_out_of_date) void askToSyncDealRows(dealBoard, dealId, dealAddress)
  }

  /** On opening Liquidity or Construction Accounts: one prompt per deal still out of date, one after another. */
  function askToSyncEveryDealStillOutOfDate(): void {
    for (const deal of liquidityStore.importedDeals) {
      if (deal.liquidity_rows_out_of_date) void askToSyncDealRows(deal.deal_board, deal.deal_id, deal.deal_address)
    }
  }

  /** After a deal is marked Dead: offer to remove its open rows, and to add the earnest money back. */
  async function offerToRemoveOpenRowsOfDeadDeal(dealBoard: LiquidityDealBoard, dealId: string, dealAddress: string): Promise<void> {
    await refreshImportedDeals()
    const deal = importedDeal(dealBoard, dealId)
    if (!deal || deal.open_row_count === 0) return
    if (!window.confirm(`${dealAddress} is dead. Remove its ${deal.open_row_count} open liquidity rows? Done rows stay.`)) return
    const refundEarnestMoney = window.confirm('Add the earnest money deposit back as money in, a week from today?')
    await liquidityStore.removeOpenDealRows(dealBoard, dealId, refundEarnestMoney ? addDays(todayISO(), 7) : null)
  }

  /** Before deleting a deal (its open rows go with it): offer to add the earnest money back as money in. */
  async function offerEarnestMoneyRefundBeforeDeletingDeal(dealBoard: LiquidityDealBoard, dealId: string): Promise<void> {
    await refreshImportedDeals()
    const deal = importedDeal(dealBoard, dealId)
    if (!deal || deal.open_row_count === 0) return
    if (window.confirm(`Its ${deal.open_row_count} open liquidity rows go with it. Add the earnest money deposit back as money in, a week from today?`)) {
      await liquidityStore.removeOpenDealRows(dealBoard, dealId, addDays(todayISO(), 7))
    }
  }

  return {
    importedDeal, boughtCopyInLiquidity, refreshImportedDeals, offerToRemoveOpenRowsOfDeadDeal, offerEarnestMoneyRefundBeforeDeletingDeal,
    askToSyncDealRows, askToSyncDealRowsIfTheSaveChangedThem, askToSyncEveryDealStillOutOfDate,
  }
}
