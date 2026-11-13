import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { linkedConstructionAccountStatus } from '../test/fixtures/constructionAccountStatus'
import type { ConstructionAccountWriteResult } from '../types/constructionAccount'

const api = vi.hoisted(() => ({ list: vi.fn(), saveLink: vi.fn(), saveRehabFigures: vi.fn() }))
vi.mock('../api/constructionAccount', () => ({ constructionAccountApi: api }))

import { figureChangesBetween, useConstructionAccountStore } from './constructionAccountStore'
import { useLiquidityTimelineChangePromptStore } from './liquidityTimelineChangePromptStore'

function result(changesTheTimeline: boolean, previewOnly: boolean): ConstructionAccountWriteResult {
  const before = linkedConstructionAccountStatus()
  return {
    was_preview_only: previewOnly, status_before: before, status_after: { ...before, rehab_cost_dollars: 58000 },
    changes_the_liquidity_timeline: changesTheTimeline, liquidity_row_changes: null, row_descriptions_marked_done: [],
    balance_left_in_the_account_dollars: null,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  for (const mock of Object.values(api)) mock.mockReset()
  api.list.mockResolvedValue({ totals: null, accounts: [] })
})

describe('every construction account edit (Requirement 1)', () => {
  it('previews first; a change that moves no row saves at once with "Saved", no prompt', async () => {
    api.saveLink.mockImplementation(async (_id, _data, options) => result(false, !!options?.previewOnly))
    const saved = await useConstructionAccountStore().saveLink('deal-1', {
      construction_mercury_account_id: 'construction', primary_checking_mercury_account_id: 'checking',
      loan_draws_pulled_before_construction_account_dollars: 0, rehab_payments_made_before_construction_account_dollars: 0,
      minimum_balance_to_keep_in_construction_account_dollars: 1000,
    })
    expect(saved).toBe(true)
    expect(api.saveLink.mock.calls.map(call => !!call[2]?.previewOnly)).toEqual([true, false])
    const promptStore = useLiquidityTimelineChangePromptStore()
    expect(promptStore.isOpen).toBe(false)
    expect(promptStore.notice?.message).toBe('Saved')
  })

  it('a change that moves the timeline asks; nothing is saved until Confirm', async () => {
    api.saveRehabFigures.mockImplementation(async (_id, _data, options) => result(true, !!options?.previewOnly))
    const answer = useConstructionAccountStore().saveRehabFigures('deal-1', { actual_rehab_cost_dollars: 58000 })
    const promptStore = useLiquidityTimelineChangePromptStore()
    await vi.waitFor(() => expect(promptStore.open?.preview?.rowChanges).toBeDefined())
    expect(api.saveRehabFigures.mock.calls.every(call => call[2]?.previewOnly)).toBe(true)
    expect(promptStore.open?.preview?.figureChanges).toEqual([{ label: 'Rehab cost', before: '$50,000', after: '$58,000' }])
    await promptStore.confirm()
    await expect(answer).resolves.toBe(true)
    expect(api.saveRehabFigures.mock.calls.filter(call => !call[2]?.previewOnly)).toHaveLength(1)
  })

  it('lists only the figures that move', () => {
    const before = linkedConstructionAccountStatus()
    expect(figureChangesBetween(before, before)).toEqual([])
    expect(figureChangesBetween(before, { ...before, safe_to_steal_now_dollars: 15000 }).map(change => change.label)).toEqual(['Safe to steal now'])
  })
})
