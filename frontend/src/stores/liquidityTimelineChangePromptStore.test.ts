import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DealCashRowChanges } from '../types/liquidity'
import {
  NOTICE_VISIBLE_MILLISECONDS, changedRowCountOf, useLiquidityTimelineChangePromptStore, type LiquidityTimelineChangePreview,
  type LiquidityTimelineChangeRequest,
} from './liquidityTimelineChangePromptStore'

function preview(updated: number): LiquidityTimelineChangePreview {
  const rowChanges = { deal_board: 'bought', deal_id: 'd', deal_address: '12 Oak St', changes: [], milestone_date_changes: [],
                       change_counts: { added: 0, updated, removed: 0 } } as unknown as DealCashRowChanges
  return { rowChanges, figureChanges: [], rowDescriptionsMarkedDone: [] }
}

function request(dealKey: string, overrides: Partial<LiquidityTimelineChangeRequest> = {}): LiquidityTimelineChangeRequest {
  return { dealKey, title: `Change ${dealKey}`, loadPreview: vi.fn(async () => preview(1)), confirm: vi.fn(async () => 1), ...overrides }
}

beforeEach(() => {
  vi.useFakeTimers()
  setActivePinia(createPinia())
})
afterEach(() => vi.useRealTimers())

describe('the timeline change prompt (Requirement 1)', () => {
  it('Confirm saves and resolves true; Cancel saves nothing and resolves false', async () => {
    const store = useLiquidityTimelineChangePromptStore()
    const confirmed = request('bought:a')
    const answer = store.ask(confirmed)
    await vi.waitFor(() => expect(store.open?.preview?.rowChanges).toBeDefined())
    await store.confirm()
    await expect(answer).resolves.toBe(true)
    expect(confirmed.confirm).toHaveBeenCalledTimes(1)

    const cancelled = request('bought:b')
    const secondAnswer = store.ask(cancelled)
    store.cancel()
    await expect(secondAnswer).resolves.toBe(false)
    expect(cancelled.confirm).not.toHaveBeenCalled()
  })

  it('one prompt at a time: another deal waits in the queue', () => {
    const store = useLiquidityTimelineChangePromptStore()
    void store.ask(request('bought:a'))
    void store.ask(request('bought:b'))
    expect(store.open?.request?.dealKey).toBe('bought:a')
    expect(store.queue.map(entry => entry.request?.dealKey)).toEqual(['bought:b'])
    store.cancel()
    expect(store.open?.request?.dealKey).toBe('bought:b')
  })

  it('a second change for the open deal merges into its prompt (read again), never a second prompt', async () => {
    const store = useLiquidityTimelineChangePromptStore()
    const first = store.ask(request('bought:a'))
    const newer = request('bought:a', { loadPreview: vi.fn(async () => preview(3)) })
    const second = store.ask(newer)
    expect(store.queue).toHaveLength(0)
    await vi.waitFor(() => expect(store.open?.preview?.rowChanges?.change_counts.updated).toBe(3))
    await store.confirm()
    await expect(first).resolves.toBe(true)
    await expect(second).resolves.toBe(true)
    expect(newer.confirm).toHaveBeenCalledTimes(1)
  })

  it('a bank report is OK-only, and merges into an open prompt of the same deal', async () => {
    const store = useLiquidityTimelineChangePromptStore()
    store.reportFromTheBank({ dealKey: 'bought:a', title: 'From the bank', preview: preview(2) })
    expect(store.isABankReport).toBe(true)
    await store.confirm()
    expect(store.isOpen).toBe(false)

    const pending = request('bought:b')
    void store.ask(pending)
    store.reportFromTheBank({ dealKey: 'bought:b', title: 'From the bank', preview: preview(2) })
    expect(store.queue).toHaveLength(0)
    expect(store.isABankReport).toBe(false)
    await vi.waitFor(() => expect(pending.loadPreview).toHaveBeenCalledTimes(2))
  })

  it('one notice that updates in place, then goes', () => {
    const store = useLiquidityTimelineChangePromptStore()
    store.showTimelineUpdated(2)
    store.showTimelineUpdated(3)
    expect(store.notice?.message).toBe('Liquidity timeline updated: 2 edits · 5 rows')
    vi.advanceTimersByTime(NOTICE_VISIBLE_MILLISECONDS + 1)
    expect(store.notice).toBeNull()
  })

  it('a failed save keeps the prompt open with the reason, and saves nothing more', async () => {
    const store = useLiquidityTimelineChangePromptStore()
    void store.ask(request('bought:a', { confirm: vi.fn(async () => { throw { response: { data: { detail: 'Mercury did not answer' } } } }) }))
    await vi.waitFor(() => expect(store.open?.preview?.rowChanges).toBeDefined())
    await store.confirm()
    expect(store.isOpen).toBe(true)
    expect(store.open?.errorMessage).toBe('Mercury did not answer')
  })

  it('counts rows changed and rows marked done', () => {
    expect(changedRowCountOf({ ...preview(2), rowDescriptionsMarkedDone: ['Deposit'] })).toBe(3)
  })
})
