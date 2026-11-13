import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DealCashRowChanges, ImportedLiquidityDeal } from '../types/liquidity'

const liquidityApi = vi.hoisted(() => ({
  getImportedDeals: vi.fn(), previewDealImport: vi.fn(), importDeal: vi.fn(), getTransactions: vi.fn(),
}))
vi.mock('../api/liquidity', () => ({ liquidityApi }))

import { useLiquidityTimelineChangePromptStore } from '../stores/liquidityTimelineChangePromptStore'
import { useLiquidityStore } from '../stores/liquidityStore'
import { useDealLiquidityRows } from './useDealLiquidityRows'

function importedDeal(liquidityRowsOutOfDate: boolean, dealId = 'deal-1'): ImportedLiquidityDeal {
  return {
    deal_board: 'bought', deal_id: dealId, deal_address: '12 Oak St', my_deals_deal_id_it_was_moved_from: null,
    liquidity_rows_out_of_date: liquidityRowsOutOfDate, open_row_count: 3, done_row_count: 0, overdue_open_row_count: 0,
    late_refi_row_count: 0, refi_is_late: false, milestones: [],
  }
}

const ONE_ROW_UPDATED: DealCashRowChanges = {
  deal_board: 'bought', deal_id: 'deal-1', deal_address: '12 Oak St', changes: [],
  change_counts: { added: 0, updated: 1, removed: 0 } as DealCashRowChanges['change_counts'], milestone_date_changes: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
  for (const mock of Object.values(liquidityApi)) mock.mockReset()
  liquidityApi.previewDealImport.mockResolvedValue(ONE_ROW_UPDATED)
  liquidityApi.importDeal.mockResolvedValue(ONE_ROW_UPDATED)
  liquidityApi.getTransactions.mockResolvedValue([])
})

describe('after a deal save', () => {
  it('a deal that is not in the timeline asks nothing, and reads nothing', async () => {
    await useDealLiquidityRows().askToSyncDealRowsIfTheSaveChangedThem('bought', 'deal-1', '12 Oak St')
    expect(liquidityApi.getImportedDeals).not.toHaveBeenCalled()
    expect(useLiquidityTimelineChangePromptStore().isOpen).toBe(false)
  })

  it('an imported deal the save did not change asks nothing', async () => {
    useLiquidityStore().importedDeals = [importedDeal(false)]
    liquidityApi.getImportedDeals.mockResolvedValue([importedDeal(false)])
    await useDealLiquidityRows().askToSyncDealRowsIfTheSaveChangedThem('bought', 'deal-1', '12 Oak St')
    expect(useLiquidityTimelineChangePromptStore().isOpen).toBe(false)
  })

  it('an imported deal the save changed opens the prompt at once; Confirm re-syncs it', async () => {
    useLiquidityStore().importedDeals = [importedDeal(false)]
    liquidityApi.getImportedDeals.mockResolvedValue([importedDeal(true)])
    await useDealLiquidityRows().askToSyncDealRowsIfTheSaveChangedThem('bought', 'deal-1', '12 Oak St')
    const promptStore = useLiquidityTimelineChangePromptStore()
    expect(promptStore.isOpen).toBe(true)
    expect(promptStore.open?.request?.dealKey).toBe('bought:deal-1')
    await vi.waitFor(() => expect(promptStore.open?.preview?.rowChanges).toEqual(ONE_ROW_UPDATED))
    await promptStore.confirm()
    expect(liquidityApi.importDeal).toHaveBeenCalledWith('bought', 'deal-1', expect.any(String), [])
    expect(promptStore.notice?.rowCount).toBe(1)
  })

  it('Cancel changes nothing', async () => {
    useLiquidityStore().importedDeals = [importedDeal(true)]
    liquidityApi.getImportedDeals.mockResolvedValue([importedDeal(true)])
    await useDealLiquidityRows().askToSyncDealRowsIfTheSaveChangedThem('bought', 'deal-1', '12 Oak St')
    useLiquidityTimelineChangePromptStore().cancel()
    expect(liquidityApi.importDeal).not.toHaveBeenCalled()
  })
})

describe('on opening Liquidity or Construction Accounts', () => {
  it('queues one prompt per deal still out of date', () => {
    useLiquidityStore().importedDeals = [importedDeal(true, 'deal-1'), importedDeal(false, 'deal-2'), importedDeal(true, 'deal-3')]
    useDealLiquidityRows().askToSyncEveryDealStillOutOfDate()
    const promptStore = useLiquidityTimelineChangePromptStore()
    expect(promptStore.open?.request?.dealKey).toBe('bought:deal-1')
    expect(promptStore.queue.map(entry => entry.request?.dealKey)).toEqual(['bought:deal-3'])
  })
})
