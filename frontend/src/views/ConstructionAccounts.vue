<script setup lang="ts">
/**
 * Construction accounts (tasks/todo/ConstructionAccountPerRehab.md): one card per Bought BRRRR deal between its
 * purchase and its refi, with every number of its rehab's own Mercury account, and the totals across them.
 *
 * Each card starts closed, as a two-row summary, so every rehab fits on one screen; a click opens its detail
 * (tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md). Cards needing you come first, closed-out ones last.
 *
 * A link opens it on one deal (`?deal=<id>&open=<section>`): the card is opened, scrolled to and highlighted, and a
 * section opens (Step C0). `?open=settings` opens the settings drawer.
 */
import { computed, nextTick, onMounted, ref } from 'vue'

import ConstructionAccountCard from '../components/liquidity/constructionAccount/ConstructionAccountCard.vue'
import ConstructionAccountSettingsDrawer from '../components/liquidity/constructionAccount/ConstructionAccountSettingsDrawer.vue'
import ConstructionAccountSettingsModal from '../components/liquidity/constructionAccount/ConstructionAccountSettingsModal.vue'
import ConstructionAccountSwitchModal from '../components/liquidity/constructionAccount/ConstructionAccountSwitchModal.vue'
import ConstructionAccountTotals from '../components/liquidity/constructionAccount/ConstructionAccountTotals.vue'
import ConstructionAccountTransferModal from '../components/liquidity/constructionAccount/ConstructionAccountTransferModal.vue'
import { useDealLiquidityRows } from '../composables/useDealLiquidityRows'
import { useDeepLinkQuery } from '../composables/useDeepLinkQuery'
import { useLiveMercuryRefresh } from '../composables/useLiveMercuryRefresh'
import { readConstructionAccountLinkQuery, type ConstructionAccountSection } from '../navigation/appLinks'
import { useConstructionAccountStore } from '../stores/constructionAccountStore'
import { useLiquidityStore } from '../stores/liquidityStore'
import type { ConstructionAccountStatus } from '../types/constructionAccount'
import { constructionAccountDisplayRank, moneyBackToYouAtTheEndDollars } from '../utils/constructionAccountSummaryFigures'
import type { ConstructionAccountTransferKind } from '../utils/constructionAccountTransferRules'

const store = useConstructionAccountStore()
const { refreshImportedDeals, askToSyncEveryDealStillOutOfDate } = useDealLiquidityRows()
const linkingStatus = ref<ConstructionAccountStatus | null>(null)
const switchingStatus = ref<ConstructionAccountStatus | null>(null)
const transferring = ref<{ status: ConstructionAccountStatus; kind: ConstructionAccountTransferKind } | null>(null)
const settingsOpen = ref(false)
const refreshMessage = ref<string | null>(null)
const highlightedDealId = ref<string | null>(null)
const sectionOpenedByALink = ref<{ dealId: string; section: ConstructionAccountSection } | null>(null)
const expandedDealIds = ref<Set<string>>(new Set())

function toggleExpanded(boughtDealId: string) {
  const nextExpandedDealIds = new Set(expandedDealIds.value)
  if (nextExpandedDealIds.has(boughtDealId)) nextExpandedDealIds.delete(boughtDealId)
  else nextExpandedDealIds.add(boughtDealId)
  expandedDealIds.value = nextExpandedDealIds
}

const moneyBackToYouAtTheEndTotalDollars = computed(() => store.accounts
  .filter(status => status.is_linked && !status.closed_out_at)
  .reduce((totalDollars, status) => totalDollars + moneyBackToYouAtTheEndDollars(status), 0))

const accountsInDisplayOrder = computed(() => [...store.accounts]
  .map((status, loadedIndex) => ({ status, loadedIndex }))
  .sort((first, second) => constructionAccountDisplayRank(first.status) - constructionAccountDisplayRank(second.status) || first.loadedIndex - second.loadedIndex)
  .map(({ status }) => status))

const mercuryIsUnavailable = computed(() => store.accounts.some(status => status.mercury_is_unavailable))
const lastAmountsAsOf = computed(() => {
  const times = store.accounts.map(status => status.amounts_as_of).filter((time): time is string => !!time).sort()
  return times.length ? new Date(times[times.length - 1]!).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : null
})

// Live: the interval, focus and instant-update reads (Requirement 4). The button is a read you asked for.
const liquidityStore = useLiquidityStore()
const { isRefreshing, refreshNow, refreshInABurst } = useLiveMercuryRefresh()

async function refreshFromMercury() {
  refreshMessage.value = null
  const result = await refreshNow({ isABackgroundPoll: false })
  if (!result) refreshMessage.value = 'Mercury could not be read right now.'
  else if (result.mercury_is_unavailable) refreshMessage.value = 'Mercury did not answer; the amounts are those of the last read.'
  else await store.load()
}

const isReady = computed(() => store.hasLoaded)
const { notFoundMessage } = useDeepLinkQuery(readConstructionAccountLinkQuery, async (link) => {
  if (link.section === 'settings' && !link.boughtDealId) {
    settingsOpen.value = true
    return true
  }
  const status = link.boughtDealId ? store.accountById.get(link.boughtDealId) : undefined
  if (!status) return false
  highlightedDealId.value = status.bought_deal_id
  expandedDealIds.value = new Set([...expandedDealIds.value, status.bought_deal_id])
  if (link.section === 'link' || link.section === 'settings') linkingStatus.value = status
  else if (link.section) sectionOpenedByALink.value = { dealId: status.bought_deal_id, section: link.section }
  await nextTick()
  document.getElementById(`construction-account-${status.bought_deal_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  return true
}, isReady)

onMounted(async () => {
  await Promise.all([store.load(), refreshImportedDeals(), liquidityStore.loadSettings().catch(() => undefined),
    store.loadConnectionStatus().catch(() => undefined)])
  askToSyncEveryDealStillOutOfDate()
  void refreshFromMercury()
})
</script>

<template>
  <section class="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-6" data-testid="ca.page">
    <header class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p class="text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">Liquidity</p>
        <h1 class="mt-1 font-display text-3xl leading-tight text-fg">Construction accounts</h1>
        <p class="mt-1 max-w-2xl text-sm text-fg-muted">
          Each rehab has its own Mercury account: the lender's draws land there and the contractors are paid from it. Click a property to see everything about it.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span v-if="lastAmountsAsOf" data-testid="ca.page.as-of" class="text-xs text-fg-muted">Amounts as of {{ lastAmountsAsOf }}</span>
        <RouterLink data-testid="ca.page.timeline" to="/liquidity" class="inline-flex items-center gap-1 rounded-ctl px-2 py-1.5 text-sm font-medium text-primary hover:bg-primary/10">
          <i class="pi pi-chart-line text-xs" aria-hidden="true"></i>Timeline
        </RouterLink>
        <UiButton variant="secondary" size="sm" data-testid="ca.page.refresh" :loading="isRefreshing" @click="refreshFromMercury">
          <i class="pi pi-refresh mr-1.5 text-xs" aria-hidden="true"></i>Refresh from Mercury
        </UiButton>
        <UiIconButton data-testid="ca.page.settings" label="Construction account settings" size="md" @click="settingsOpen = true">
          <i class="pi pi-cog" aria-hidden="true"></i>
        </UiIconButton>
      </div>
    </header>

    <p v-if="notFoundMessage" data-testid="ca.page.not-found" role="status" class="rounded-ctl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">{{ notFoundMessage }}</p>
    <p v-if="mercuryIsUnavailable || refreshMessage" data-testid="ca.page.mercury-unavailable" role="status"
       class="rounded-ctl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
      {{ refreshMessage ?? 'Mercury did not answer; the amounts are those of the last read.' }}
    </p>
    <p v-if="store.loadErrorMessage" role="alert" class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">{{ store.loadErrorMessage }}</p>

    <ConstructionAccountTotals v-if="store.totals && store.totals.linked_account_count" :totals="store.totals" :money-back-to-you-at-the-end-total-dollars="moneyBackToYouAtTheEndTotalDollars" />

    <div v-if="store.isLoading && !store.hasLoaded" data-testid="ca.page.loading" class="space-y-3">
      <UiSkeleton class="h-40" /><UiSkeleton class="h-40" />
    </div>
    <UiEmptyState v-else-if="store.hasLoaded && !store.accounts.length" data-testid="ca.page.empty" icon="pi pi-building-columns">
      No rehab to track yet
      <template #description>A Bought BRRRR deal in the liquidity timeline shows here until its refi, ready for its construction account.</template>
      <template #actions>
        <RouterLink to="/bought-deals" class="text-sm font-medium text-primary underline">Go to Bought deals</RouterLink>
      </template>
    </UiEmptyState>

    <div class="space-y-3">
      <ConstructionAccountCard
        v-for="status in accountsInDisplayOrder"
        :key="status.bought_deal_id"
        :status="status"
        :is-expanded="expandedDealIds.has(status.bought_deal_id)"
        :is-highlighted="highlightedDealId === status.bought_deal_id"
        :open-section="sectionOpenedByALink?.dealId === status.bought_deal_id ? sectionOpenedByALink.section : null"
        @link="(chosen) => (linkingStatus = chosen)"
        @switch-account="(chosen) => (switchingStatus = chosen)"
        @transfer="(chosen, kind) => (transferring = { status: chosen, kind })"
        @toggle="(chosen) => toggleExpanded(chosen.bought_deal_id)"
      />
    </div>

    <ConstructionAccountSettingsModal :open="linkingStatus !== null" :status="linkingStatus" @close="linkingStatus = null" />
    <ConstructionAccountSwitchModal :open="switchingStatus !== null" :status="switchingStatus" @close="switchingStatus = null" />
    <!-- After a transfer: read the bank at once, then at 2, 5, 10, 20 and 40 s, until the feed shows it. -->
    <ConstructionAccountTransferModal :open="transferring !== null" :status="transferring?.status ?? null" :kind="transferring?.kind ?? 'deposit'"
                                      @close="transferring = null" @transferred="refreshInABurst(result => result.construction_accounts_changed)" />
    <ConstructionAccountSettingsDrawer :open="settingsOpen" @close="settingsOpen = false" @saved="liquidityStore.useSavedSettings" />
  </section>
</template>
