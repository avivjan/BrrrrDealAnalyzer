// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import type { ConstructionAccountRefreshResult } from '../types/constructionAccount'
import type { DealCashRowChanges } from '../types/liquidity'

const api = vi.hoisted(() => ({ refresh: vi.fn(), lastChange: vi.fn(), list: vi.fn(), connectionStatus: vi.fn() }))
vi.mock('../api/constructionAccount', () => ({ constructionAccountApi: api }))

import { useConstructionAccountStore } from '../stores/constructionAccountStore'
import { useLiquidityStore } from '../stores/liquidityStore'
import { useLiquidityTimelineChangePromptStore } from '../stores/liquidityTimelineChangePromptStore'
import { BURST_READ_OFFSETS_SECONDS, useLiveMercuryRefresh } from './useLiveMercuryRefresh'

function refreshResult(overrides: Partial<ConstructionAccountRefreshResult> = {}): ConstructionAccountRefreshResult {
  return {
    refreshed_deal_count: 1, changed_row_count: 0, mercury_is_unavailable: false, next_mercury_read_not_before: null,
    cash_balance_changed: false, construction_accounts_changed: false, cash_balance_last_changed_at: null,
    construction_accounts_last_changed_at: null, bank_reported_row_changes: [], ...overrides,
  }
}

function rowChangesOfOneDeal(updated: number): DealCashRowChanges {
  return {
    deal_board: 'bought', deal_id: 'deal-1', deal_address: '12 Oak St', changes: [],
    change_counts: { added: 0, updated, removed: 0 } as DealCashRowChanges['change_counts'], milestone_date_changes: [],
  }
}

let live: ReturnType<typeof useLiveMercuryRefresh>
let unmount: () => void

function mountThePage() {
  const Page = defineComponent({ setup() { live = useLiveMercuryRefresh(); return () => h('div') } })
  const wrapper = mount(Page)
  unmount = () => wrapper.unmount()
}

function setTabVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
}

beforeEach(() => {
  vi.useFakeTimers()
  setActivePinia(createPinia())
  setTabVisibility('visible')
  api.refresh.mockReset().mockResolvedValue(refreshResult())
  // Every later check answers "nothing new" unless a test says otherwise.
  api.lastChange.mockReset().mockResolvedValue({ last_changed_at: null, cash_balance_last_changed_at: null, construction_accounts_last_changed_at: null })
  api.list.mockReset().mockResolvedValue({ totals: null, accounts: [] })
})
afterEach(() => { unmount?.(); vi.useRealTimers() })

describe('useLiveMercuryRefresh', () => {
  it('reads every interval as a background poll, and not while the tab is hidden', async () => {
    useLiquidityStore().settings.construction_account_refresh_interval_seconds = 20
    mountThePage()
    await vi.advanceTimersByTimeAsync(20_000)
    expect(api.refresh).toHaveBeenCalledTimes(1)
    expect(api.refresh.mock.calls[0]![1]).toBe(true)
    setTabVisibility('hidden')
    await vi.advanceTimersByTimeAsync(40_000)
    expect(api.refresh).toHaveBeenCalledTimes(1)
  })

  it('waits while the server asks to (back-off), but a read you ask for goes through', async () => {
    mountThePage()
    useConstructionAccountStore().nextMercuryReadNotBefore = new Date(Date.now() + 60_000).toISOString()
    expect(await live.refreshNow()).toBeNull()
    expect(api.refresh).not.toHaveBeenCalled()
    await live.refreshNow({ isABackgroundPoll: false })
    expect(api.refresh).toHaveBeenCalledWith(expect.any(String), false)
  })

  it('a wait far beyond the longest back-off is a clock difference, not a back-off: the read goes ahead', async () => {
    mountThePage()
    useConstructionAccountStore().nextMercuryReadNotBefore = new Date(Date.now() + 60 * 24 * 3600 * 1000).toISOString()
    await live.refreshNow()
    expect(api.refresh).toHaveBeenCalledTimes(1)
  })

  it('reads when the window regains focus, at most once per 5 seconds', async () => {
    mountThePage()
    window.dispatchEvent(new Event('focus'))
    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(api.refresh).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(5_001)
    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(api.refresh).toHaveBeenCalledTimes(2)
  })

  it('does not read on focus when the setting is off', async () => {
    useLiquidityStore().settings.construction_account_refresh_when_window_regains_focus = false
    mountThePage()
    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(api.refresh).not.toHaveBeenCalled()
  })

  it('a burst reads at each offset and stops once the transfer shows', async () => {
    useLiquidityStore().settings.construction_account_refresh_interval_seconds = 600   // only the burst reads here
    mountThePage()
    api.refresh.mockResolvedValueOnce(refreshResult()).mockResolvedValueOnce(refreshResult({ construction_accounts_changed: true }))
    live.refreshInABurst(result => result.construction_accounts_changed)
    await vi.advanceTimersByTimeAsync(BURST_READ_OFFSETS_SECONDS[BURST_READ_OFFSETS_SECONDS.length - 1]! * 1000)
    expect(api.refresh).toHaveBeenCalledTimes(2)
  })

  it('a cash balance change updates the balance and the starting balance, with no prompt', async () => {
    mountThePage()
    const liquidityStore = useLiquidityStore()
    const applyMercuryBalance = vi.spyOn(liquidityStore, 'applyMercuryBalance').mockResolvedValue()
    api.refresh.mockResolvedValueOnce(refreshResult({ cash_balance_changed: true }))
    await live.refreshNow()
    expect(applyMercuryBalance).toHaveBeenCalledTimes(1)
    expect(useLiquidityTimelineChangePromptStore().isOpen).toBe(false)
  })

  it('rows the bank changed open the OK-only "updated from the bank" modal and reload the cards', async () => {
    mountThePage()
    const constructionAccountStore = useConstructionAccountStore()
    constructionAccountStore.hasLoaded = true
    api.refresh.mockResolvedValueOnce(refreshResult({
      construction_accounts_changed: true, bank_reported_row_changes: [rowChangesOfOneDeal(1), { ...rowChangesOfOneDeal(0), deal_id: 'deal-2' }],
    }))
    await live.refreshNow()
    const promptStore = useLiquidityTimelineChangePromptStore()
    expect(api.list).toHaveBeenCalledTimes(1)
    expect(promptStore.isABankReport).toBe(true)
    expect(promptStore.open?.bankReport?.dealKey).toBe('bought:deal-1')
    expect(promptStore.queue).toHaveLength(0)   // a deal whose rows did not change opens nothing
  })

  it('with instant updates on, checks the database every 5 seconds and reloads what moved', async () => {
    const constructionAccountStore = useConstructionAccountStore()
    constructionAccountStore.hasLoaded = true
    mountThePage()
    api.lastChange
      .mockResolvedValueOnce({ last_changed_at: 'a', cash_balance_last_changed_at: 'a', construction_accounts_last_changed_at: 'a' })
      .mockResolvedValue({ last_changed_at: 'b', cash_balance_last_changed_at: 'a', construction_accounts_last_changed_at: 'b' })   // and stays
    constructionAccountStore.connectionStatus = {
      workspaces: [{ instant_updates_are_on: true } as never], read_token_environment_variable_name_pattern: '', transfer_token_environment_variable_name_pattern: '',
    }
    await flushPromises()
    await vi.advanceTimersByTimeAsync(10_000)
    expect(api.lastChange).toHaveBeenCalledTimes(3)   // the baseline at once, then every 5 seconds
    expect(api.list).toHaveBeenCalledTimes(1)
    expect(api.refresh).not.toHaveBeenCalled()
  })

  it('rows an instant update changed open the "updated from the bank" window', async () => {
    mountThePage()
    api.lastChange
      .mockResolvedValueOnce({ last_changed_at: 'a', cash_balance_last_changed_at: 'a', construction_accounts_last_changed_at: 'a', last_instant_update_at: null })
      .mockResolvedValue({ last_changed_at: 'b', cash_balance_last_changed_at: 'a', construction_accounts_last_changed_at: 'b',
                               last_instant_update_at: 'b', bank_reported_row_changes_of_last_instant_update: [rowChangesOfOneDeal(1)] })
    useConstructionAccountStore().connectionStatus = {
      workspaces: [{ instant_updates_are_on: true } as never], read_token_environment_variable_name_pattern: '', transfer_token_environment_variable_name_pattern: '',
    }
    await flushPromises()
    await vi.advanceTimersByTimeAsync(10_000)
    const promptStore = useLiquidityTimelineChangePromptStore()
    expect(promptStore.isABankReport).toBe(true)
    expect(promptStore.open?.bankReport?.dealKey).toBe('bought:deal-1')
  })
})
