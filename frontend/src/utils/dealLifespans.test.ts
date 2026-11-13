import { describe, expect, it } from 'vitest'

import type { DealMilestoneState, ImportedLiquidityDeal } from '../types/liquidity'
import { dealLifespansOf } from './dealLifespans'

function deal(dealId: string, contract: string, refi: string, overrides: { refiApproved?: boolean; contractApprovedOn?: string } = {}): ImportedLiquidityDeal {
  const milestones: DealMilestoneState[] = [
    { milestone: 'contract_signed', planned_date: contract, approved_at: overrides.contractApprovedOn ? `${overrides.contractApprovedOn}T12:00:00Z` : null, is_overdue: false },
    { milestone: 'refi_closed', planned_date: refi, approved_at: overrides.refiApproved ? `${refi}T12:00:00Z` : null, is_overdue: false },
  ]
  return { deal_board: 'bought', deal_id: dealId, deal_address: dealId, my_deals_deal_id_it_was_moved_from: null, liquidity_rows_out_of_date: false,
           open_row_count: 1, done_row_count: 0, overdue_open_row_count: 0, late_refi_row_count: 0, refi_is_late: false, milestones }
}

describe('dealLifespansOf', () => {
  it('one lane per deal in progress, ordered by their start, from the contract to the refi', () => {
    const lifespans = dealLifespansOf([deal('b', '2026-12-01', '2027-06-01'), deal('a', '2026-10-01', '2027-04-01')], '2026-11-05')
    expect(lifespans.map(lifespan => [lifespan.dealKey, lifespan.startDate, lifespan.endDate, lifespan.laneIndex])).toEqual([
      ['bought:a', '2026-10-01', '2027-04-01', 0], ['bought:b', '2026-12-01', '2027-06-01', 1],
    ])
    expect(new Set(lifespans.map(lifespan => lifespan.laneIndex)).size).toBe(lifespans.length)
  })

  it('a deal whose refi is approved is over; a late refi runs through today; an approved contract starts on its day', () => {
    const lifespans = dealLifespansOf([
      deal('done', '2026-01-01', '2026-06-01', { refiApproved: true }),
      deal('late', '2026-03-01', '2026-10-01', { contractApprovedOn: '2026-03-04' }),
    ], '2026-11-05')
    expect(lifespans).toEqual([{ dealKey: 'bought:late', startDate: '2026-03-04', endDate: '2026-11-05', refiIsLate: true, laneIndex: 0 }])
  })
})
