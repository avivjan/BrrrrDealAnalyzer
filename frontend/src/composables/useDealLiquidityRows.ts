/**
 * A BRRRR deal's rows in the liquidity timeline, as the deal boards see them (tasks/todo/DealCashInLiquidity.md):
 * whether the deal is imported (directly, or through its Bought copy), and the prompts when the deal dies or is
 * deleted (its open rows go; the earnest money may come back as money in).
 */
import { useLiquidityStore } from '../stores/liquidityStore'
import type { ImportedLiquidityDeal, LiquidityDealBoard } from '../types/liquidity'
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

  return { importedDeal, boughtCopyInLiquidity, refreshImportedDeals, offerToRemoveOpenRowsOfDeadDeal, offerEarnestMoneyRefundBeforeDeletingDeal }
}
