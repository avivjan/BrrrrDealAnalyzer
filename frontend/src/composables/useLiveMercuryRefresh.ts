/**
 * Mercury as close to live as it allows (tasks/todo/ConstructionAccountPerRehab.md, Requirement 4), for the Liquidity
 * and Construction Accounts pages:
 * - a read every `construction_account_refresh_interval_seconds` while the tab is visible (paused while hidden);
 * - a read when the window regains focus (the setting), not more than once per 5 seconds;
 * - a burst after a transfer: at once, then at 2, 5, 10, 20 and 40 seconds;
 * - while instant updates are on for an LLC, a check of our own database every 5 seconds (no Mercury call).
 * The server paces every read per LLC (10 s floor, back-off on 429); the page also waits for
 * `next_mercury_read_not_before` before its next background read.
 *
 * What a read finds is shown without a reload: the construction account cards and the timeline's rows when a linked
 * account moved (with the "Timeline updated from the bank" modal when rows changed), and the cash balance and the
 * timeline's starting balance when the LLC's cash moved (a fact from the bank: no prompt).
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { constructionAccountApi } from '../api/constructionAccount'
import { useConstructionAccountStore } from '../stores/constructionAccountStore'
import { useLiquidityStore } from '../stores/liquidityStore'
import { useLiquidityTimelineChangePromptStore } from '../stores/liquidityTimelineChangePromptStore'
import type { ConstructionAccountRefreshResult, MercuryLastChange } from '../types/constructionAccount'
import { todayISO } from '../utils/liquidityEngine'

export const DEFAULT_REFRESH_INTERVAL_SECONDS = 30
export const MINIMUM_MILLISECONDS_BETWEEN_FOCUS_REFRESHES = 5000
export const INSTANT_UPDATES_CHECK_MILLISECONDS = 5000
export const BURST_READ_OFFSETS_SECONDS = [0, 2, 5, 10, 20, 40] as const

function changedRowCount(rowChanges: ConstructionAccountRefreshResult['bank_reported_row_changes'][number]): number {
  const counts = rowChanges.change_counts
  return counts.added + counts.updated + counts.removed
}

export function useLiveMercuryRefresh() {
  const liquidityStore = useLiquidityStore()
  const constructionAccountStore = useConstructionAccountStore()
  const promptStore = useLiquidityTimelineChangePromptStore()

  const isRefreshing = ref(false)
  const mercuryIsUnavailable = ref(false)
  const lastRefreshFailed = ref(false)

  let intervalTimer: ReturnType<typeof setInterval> | null = null
  let instantUpdatesTimer: ReturnType<typeof setInterval> | null = null
  const burstTimers: ReturnType<typeof setTimeout>[] = []
  let lastFocusRefreshAtMilliseconds = 0
  let lastSeenChange: MercuryLastChange | null = null

  const tabIsVisible = () => typeof document === 'undefined' || document.visibilityState !== 'hidden'
  const timelineIsLoaded = () => liquidityStore.transactions.length > 0 || liquidityStore.importedDeals.length > 0

  function serverAsksToWait(): boolean {
    const notBefore = constructionAccountStore.nextMercuryReadNotBefore
    return !!notBefore && Date.parse(notBefore) > Date.now()
  }

  async function showWhatChanged(cashBalanceChanged: boolean, constructionAccountsChanged: boolean): Promise<void> {
    const reloads: Promise<unknown>[] = []
    if (constructionAccountsChanged) {
      if (constructionAccountStore.hasLoaded) reloads.push(constructionAccountStore.load())
      if (timelineIsLoaded()) reloads.push(liquidityStore.reloadTransactionsAndImportedDeals())
    }
    if (cashBalanceChanged) reloads.push(liquidityStore.applyMercuryBalance())
    await Promise.all(reloads)
  }

  /** "Timeline updated from the bank" (OK only), once per deal whose rows changed. */
  function reportTheRowsTheBankChanged(bankReportedRowChanges: ConstructionAccountRefreshResult['bank_reported_row_changes']): void {
    for (const rowChanges of bankReportedRowChanges) {
      if (!changedRowCount(rowChanges)) continue
      promptStore.reportFromTheBank({
        dealKey: `${rowChanges.deal_board}:${rowChanges.deal_id}`,
        title: `${rowChanges.deal_address}: timeline updated from the bank`,
        preview: { rowChanges, figureChanges: [], rowDescriptionsMarkedDone: [] },
      })
    }
  }

  /** One read. A background read is skipped while the server asks to wait or the tab is hidden. */
  async function refreshNow(options: { isABackgroundPoll?: boolean } = {}): Promise<ConstructionAccountRefreshResult | null> {
    const isABackgroundPoll = options.isABackgroundPoll ?? true
    if (isRefreshing.value) return null
    if (isABackgroundPoll && (!tabIsVisible() || serverAsksToWait())) return null
    isRefreshing.value = true
    try {
      const result = await constructionAccountApi.refresh(todayISO(), isABackgroundPoll)
      lastRefreshFailed.value = false
      mercuryIsUnavailable.value = result.mercury_is_unavailable
      constructionAccountStore.nextMercuryReadNotBefore = result.next_mercury_read_not_before
      await showWhatChanged(result.cash_balance_changed, result.construction_accounts_changed)
      reportTheRowsTheBankChanged(result.bank_reported_row_changes)
      return result
    } catch {
      lastRefreshFailed.value = true
      return null
    } finally {
      isRefreshing.value = false
    }
  }

  /** After a transfer: read now and at each offset, until `transferShows` says the bank feed has it. */
  function refreshInABurst(transferShows: (result: ConstructionAccountRefreshResult) => boolean = () => false): void {
    stopTheBurst()
    let found = false
    for (const offsetSeconds of BURST_READ_OFFSETS_SECONDS) {
      burstTimers.push(setTimeout(async () => {
        if (found) return
        const result = await refreshNow({ isABackgroundPoll: true })
        if (result && transferShows(result)) {
          found = true
          stopTheBurst()
        }
      }, offsetSeconds * 1000))
    }
  }

  function stopTheBurst(): void {
    while (burstTimers.length) clearTimeout(burstTimers.pop()!)
  }

  /** Instant updates: our own database says when a webhook moved something; nothing is asked of Mercury. */
  async function checkForAnInstantUpdate(): Promise<void> {
    if (!tabIsVisible()) return
    let change: MercuryLastChange
    try {
      change = await constructionAccountApi.lastChange()
    } catch {
      return
    }
    const before = lastSeenChange
    lastSeenChange = change
    if (!before) return
    await showWhatChanged(change.cash_balance_last_changed_at !== before.cash_balance_last_changed_at,
      change.construction_accounts_last_changed_at !== before.construction_accounts_last_changed_at)
    if (change.last_instant_update_at && change.last_instant_update_at !== before.last_instant_update_at) {
      reportTheRowsTheBankChanged(change.bank_reported_row_changes_of_last_instant_update ?? [])
    }
  }

  function startTheInterval(): void {
    if (intervalTimer) clearInterval(intervalTimer)
    const seconds = liquidityStore.settings.construction_account_refresh_interval_seconds ?? DEFAULT_REFRESH_INTERVAL_SECONDS
    intervalTimer = setInterval(() => { void refreshNow() }, seconds * 1000)
  }

  function startTheInstantUpdatesCheckWhenOn(): void {
    const instantUpdatesAreOn = constructionAccountStore.connectionStatus?.workspaces.some(workspace => workspace.instant_updates_are_on) ?? false
    if (instantUpdatesAreOn && !instantUpdatesTimer) {
      instantUpdatesTimer = setInterval(() => { void checkForAnInstantUpdate() }, INSTANT_UPDATES_CHECK_MILLISECONDS)
    } else if (!instantUpdatesAreOn && instantUpdatesTimer) {
      clearInterval(instantUpdatesTimer)
      instantUpdatesTimer = null
    }
  }

  function onTheWindowRegainedFocus(): void {
    if (!tabIsVisible() || liquidityStore.settings.construction_account_refresh_when_window_regains_focus === false) return
    const now = Date.now()
    if (now - lastFocusRefreshAtMilliseconds < MINIMUM_MILLISECONDS_BETWEEN_FOCUS_REFRESHES) return
    lastFocusRefreshAtMilliseconds = now
    void refreshNow()
  }

  watch(() => liquidityStore.settings.construction_account_refresh_interval_seconds, () => { if (intervalTimer) startTheInterval() })
  watch(() => constructionAccountStore.connectionStatus, startTheInstantUpdatesCheckWhenOn)

  onMounted(() => {
    startTheInterval()
    startTheInstantUpdatesCheckWhenOn()
    window.addEventListener('focus', onTheWindowRegainedFocus)
    document.addEventListener('visibilitychange', onTheWindowRegainedFocus)
  })

  onBeforeUnmount(() => {
    if (intervalTimer) clearInterval(intervalTimer)
    if (instantUpdatesTimer) clearInterval(instantUpdatesTimer)
    stopTheBurst()
    window.removeEventListener('focus', onTheWindowRegainedFocus)
    document.removeEventListener('visibilitychange', onTheWindowRegainedFocus)
  })

  return { isRefreshing, mercuryIsUnavailable, lastRefreshFailed, refreshNow, refreshInABurst }
}
