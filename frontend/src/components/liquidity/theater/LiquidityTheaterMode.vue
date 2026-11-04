<script setup lang="ts">
/**
 * The liquidity page (tasks/todo/LiquidityTheaterMode.md, section A; tasks/todo/LiquidityTheaterOnly.md): the
 * chart takes the whole viewport, over the app's sidebar and topbar, with everything else in overlays:
 *
 * - top bar: the headline figures as chips (Today's balance opens the Mercury breakdown, the overdue chip opens
 *   the overdue rows), and a floating action bar (Today, Mercury, Settings, + Add Flow, Legend, browser
 *   fullscreen, theme, search, shortcuts, ×);
 * - the legend (deals, their overdue rows, recurring series), the deals & milestones bottom sheet, and a full
 *   modal for a clicked day. Hovering a day shows a floating preview.
 *
 * Esc closes the topmost layer first (day modal, popovers, deals sheet), then leaves the page (`leave`, the same as
 * ×); the legend is a panel that stays until toggled. Shortcuts: F browser fullscreen, L legend, D deals, ? help;
 * never while typing, and never while another dialog (one of the view's modals, the command palette, Settings) is
 * open.
 *
 * Only `opacity` animates on this root and the chart's ancestors: the chart re-measures from a ResizeObserver.
 * The legend, the sheet and the popovers move with `transform` beside it.
 */
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { OPEN_COMMAND_PALETTE_INJECTION_KEY } from '../../shell/commandPaletteInjection'
import { resolvedTheme, toggleTheme } from '../../../design/theme'
import { useLiquidityStore } from '../../../stores/liquidityStore'
import type { DealMilestone, DealMilestoneState, ImportedLiquidityDeal } from '../../../types/liquidity'
import { todayISO } from '../../../utils/liquidityEngine'
import { lowestBalanceInNextDays, nextOpenTransaction } from '../../../utils/liquidityUpcoming'
import { doneTransactionsOnDate } from './legendRows'
import { formatMoney, formatSignedMoney } from '../../../utils/money'
import DealAttributionTag from '../DealAttributionTag.vue'
import OverdueTransactionsStrip from '../OverdueTransactionsStrip.vue'
import TimelineChart from '../TimelineChart.vue'
import DayTransactionsModal from './DayTransactionsModal.vue'
import DealLegendPanel from './DealLegendPanel.vue'
import DealMilestonesBottomSheet from './DealMilestonesBottomSheet.vue'

/** The view's headline figures, already formatted (the same four as its KPI cards). */
export interface LiquidityHeadlineFigures {
  balance: string
  balanceTone: string
  min: string
  minTone: string
  minDate: string | null
  daysToNegative: string
  daysTone: string
  reserve: string
}

const props = defineProps<{
  headlineFigures: LiquidityHeadlineFigures
  /** One of the view's own modals is open: it owns Esc and the keyboard. */
  isAnotherDialogOpen: boolean
  milestoneKeyBeingApproved?: string | null
}>()

const emit = defineEmits<{
  /** Esc with nothing open, or ×: leave the liquidity page. */
  (e: 'leave'): void
  (e: 'addFlow', date?: string): void
  (e: 'editTxn', id: string): void
  (e: 'deleteTxn', id: string): void
  (e: 'openSettings'): void
  (e: 'syncMercury'): void
  (e: 'editRecurring', ruleId: string): void
  (e: 'deleteRecurring', ruleId: string): void
  (e: 'markDone', id: string): void
  /** Undo a Done (from the legend's Transactions or the day modal). */
  (e: 'markNotDone', id: string): void
  (e: 'moveToDate', id: string, newEffectiveDate: string): void
  (e: 'changeAmount', id: string, newAmountDollars: number): void
  (e: 'bulkMarkDone', ids: string[]): void
  (e: 'bulkMoveToDate', ids: string[], newEffectiveDate: string): void
  (e: 'approveMilestone', deal: ImportedLiquidityDeal, milestone: DealMilestone): void
  (e: 'changeMilestone', deal: ImportedLiquidityDeal, milestone: DealMilestone, approve: boolean): void
  (e: 'reviewChanges', deal: ImportedLiquidityDeal): void
  (e: 'removeDealFromTimeline', deal: ImportedLiquidityDeal): void
}>()

const store = useLiquidityStore()
const openCommandPalette = inject(OPEN_COMMAND_PALETTE_INJECTION_KEY, null)

const rootRef = ref<HTMLElement | null>(null)
const chartRef = ref<InstanceType<typeof TimelineChart> | null>(null)

// --- layers ---------------------------------------------------------------------------------------------------
const LEGEND_OPEN_STORAGE_KEY = 'bw.liquidity.theater.legend-open'
function readLegendOpenPreference(): boolean {
  try {
    const stored = localStorage.getItem(LEGEND_OPEN_STORAGE_KEY)
    if (stored === 'true' || stored === 'false') return stored === 'true'
  } catch {
    // Remembering the choice is a convenience, not a requirement.
  }
  return typeof window !== 'undefined' && window.innerWidth >= 1024
}
const legendOpen = ref(readLegendOpenPreference())
watch(legendOpen, (isOpen) => {
  try {
    localStorage.setItem(LEGEND_OPEN_STORAGE_KEY, String(isOpen))
  } catch {
    // As above.
  }
})
const sheetOpen = ref(false)
const overduePopoverOpen = ref(false)
const balancePopoverOpen = ref(false)
const moreActionsMenuOpen = ref(false)
const shortcutsHelpOpen = ref(false)
const highlightedDealKey = ref<string | null>(null)
const dayModalDate = ref<string | null>(null)

/** The first load: nothing to draw yet. */
const isLoadingForTheFirstTime = computed(() => store.loading && store.transactions.length === 0 && store.importedDeals.length === 0)

/** "HH:MM" of the last Mercury sync. */
const mercurySyncedTime = computed(() => {
  if (!store.mercuryLastSyncedAt) return null
  const syncedAt = new Date(store.mercuryLastSyncedAt)
  return `${String(syncedAt.getHours()).padStart(2, '0')}:${String(syncedAt.getMinutes()).padStart(2, '0')}`
})

function closePopovers() {
  overduePopoverOpen.value = false
  balancePopoverOpen.value = false
  moreActionsMenuOpen.value = false
  shortcutsHelpOpen.value = false
}

// --- the day modal --------------------------------------------------------------------------------------------
const dayModalIndex = computed(() => dayModalDate.value === null ? -1 : store.series.days.findIndex(day => day.date === dayModalDate.value))
const dayModalBucket = computed(() => store.series.days[dayModalIndex.value] ?? null)
const dayModalOpeningBalanceDollars = computed(() => {
  const bucket = dayModalBucket.value
  if (!bucket) return 0
  const previousDay = store.series.days[dayModalIndex.value - 1]
  return previousDay ? previousDay.balance_dollars : bucket.balance_dollars - bucket.net_dollars
})
const milestonesOnTheModalDay = computed(() => {
  const date = dayModalDate.value
  if (!date) return []
  const entries: { deal: ImportedLiquidityDeal; state: DealMilestoneState }[] = []
  for (const deal of store.importedDeals) {
    if (deal.open_row_count === 0) continue
    for (const state of deal.milestones) if (state.planned_date === date) entries.push({ deal, state })
  }
  return entries
})
const doneTransactionsOfTheModalDay = computed(() => dayModalDate.value ? doneTransactionsOnDate(store.transactions, dayModalDate.value) : [])
function stepDayModal(direction: -1 | 1) {
  const next = store.series.days[dayModalIndex.value + direction]
  if (next) dayModalDate.value = next.date
}
function onOpenDay(date: string) {
  closePopovers()
  dayModalDate.value = date
}

// --- figures --------------------------------------------------------------------------------------------------
const todayIsoDate = todayISO()
const lowestBalanceInNext90Days = computed(() => lowestBalanceInNextDays(store.series, todayIsoDate, 90))
const nextMoneyOut = computed(() => nextOpenTransaction(store.transactions, todayIsoDate, 'money_out'))
const nextMoneyIn = computed(() => nextOpenTransaction(store.transactions, todayIsoDate, 'money_in'))
const overdueRowCount = computed(() => store.overdueMoneyOut.length + store.expectedMoneyInNotCounted.length)
const overdueMoneyOutTotalDollars = computed(() => store.overdueMoneyOut.reduce((total, txn) => total + txn.amount_dollars, 0))

const TONE_TEXT_CLASS: Record<string, string> = { negative: 'text-negative', warning: 'text-warning', positive: 'text-positive' }
function toneTextClass(tone: string): string {
  return TONE_TEXT_CLASS[tone] ?? 'text-fg'
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(isoDate: string): string {
  const [, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}`
}

// --- browser fullscreen ---------------------------------------------------------------------------------------
const isBrowserFullscreen = ref(false)
const browserFullscreenIsSupported = typeof document !== 'undefined' && typeof document.documentElement?.requestFullscreen === 'function'
function onFullscreenChange() {
  isBrowserFullscreen.value = !!document.fullscreenElement
}
async function toggleBrowserFullscreen() {
  if (!browserFullscreenIsSupported) return
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen()
  } catch {
    // The browser refused (no user gesture, or a policy): theater mode still fills the window.
  }
}

// --- keyboard -------------------------------------------------------------------------------------------------
function isTypingInAField(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null
  return !!element?.closest?.('input, textarea, select, [contenteditable="true"], [contenteditable=""]')
}

/** A dialog outside the theater (the view's modals, the command palette, Settings) owns the keyboard. */
function anotherDialogOwnsTheKeyboard(): boolean {
  if (props.isAnotherDialogOpen) return true
  const openDialogs = Array.from(document.querySelectorAll('[aria-modal="true"]'))
  return openDialogs.some(dialog => !rootRef.value?.contains(dialog))
}

/** Esc: the day modal, then a popover, then the deals sheet, then leave the page. The legend is a panel, not a layer. */
function closeTopmostLayer() {
  if (dayModalDate.value !== null) dayModalDate.value = null
  else if (overduePopoverOpen.value || balancePopoverOpen.value || moreActionsMenuOpen.value || shortcutsHelpOpen.value) closePopovers()
  else if (sheetOpen.value) sheetOpen.value = false
  else emit('leave')
}

function onKeyDown(event: KeyboardEvent) {
  if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return
  if (anotherDialogOwnsTheKeyboard()) return
  if (event.key === 'Escape') {
    event.preventDefault()
    closeTopmostLayer()
    return
  }
  if (isTypingInAField(event.target)) return
  const key = event.key.toLowerCase()
  if (key === 'f') {
    event.preventDefault()
    void toggleBrowserFullscreen()
  } else if (key === 'l') {
    event.preventDefault()
    legendOpen.value = !legendOpen.value
  } else if (key === 'd') {
    event.preventDefault()
    sheetOpen.value = !sheetOpen.value
  } else if (event.key === '?') {
    event.preventDefault()
    shortcutsHelpOpen.value = !shortcutsHelpOpen.value
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeyDown)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  // The arrow keys work at once: the focus starts on the chart.
  await nextTick()
  rootRef.value?.querySelector<HTMLElement>('[data-testid="chart.container"]')?.focus()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
})

const SHORTCUTS = [
  { key: 'F', action: 'Browser fullscreen' },
  { key: 'L', action: 'Legend' },
  { key: 'D', action: 'Deals & milestones' },
  { key: '← →', action: 'Step through days' },
  { key: 'Enter', action: 'Open the selected day' },
  { key: 'Esc', action: 'Close the top layer, then leave' },
]
</script>

<template>
  <Teleport to="body">
    <Transition name="theater-fade" appear>
      <div
        ref="rootRef"
        data-testid="theater.root"
        role="dialog"
        aria-modal="true"
        aria-labelledby="theater-heading"
        class="fixed inset-0 z-40 flex flex-col overflow-hidden bg-page text-fg"
      >
        <!-- Top bar: title, the figures as chips, the floating actions -->
        <!-- A div, not a <header>: the app topbar underneath is the page banner. -->
        <div data-testid="theater.top-bar" class="relative z-30 flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-surface/85 px-3 py-2 backdrop-blur-md sm:px-4 md:flex-nowrap">
          <div class="flex shrink-0 items-center gap-2">
            <span class="flex h-8 w-8 items-center justify-center rounded-ctl bg-primary/10 text-primary" aria-hidden="true"><i class="pi pi-chart-line text-sm"></i></span>
            <h1 id="theater-heading" class="font-display text-lg font-semibold tracking-display text-fg md:sr-only xl:not-sr-only">Liquidity Timeline</h1>
          </div>

          <div data-testid="theater.figures" class="no-scrollbar order-last flex w-full min-w-0 items-center gap-2 overflow-x-auto py-0.5 md:order-none md:w-auto md:flex-1">
            <button
              type="button"
              data-testid="theater.figure.balance"
              class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 text-left shadow-1 transition-colors duration-fast ease-standard hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              :aria-expanded="balancePopoverOpen"
              @click="overduePopoverOpen = false; balancePopoverOpen = !balancePopoverOpen"
            >
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">Today</span>
              <span class="numeric text-sm font-bold" :class="toneTextClass(headlineFigures.balanceTone)">{{ headlineFigures.balance }}</span>
              <i
                :class="store.mercurySyncing ? 'pi pi-spin pi-spinner text-fg-muted' : store.mercuryError ? 'pi pi-exclamation-triangle text-negative' : store.mercuryBalance ? 'pi pi-check-circle text-positive' : 'pi pi-wallet text-fg-muted'"
                class="text-[10px]"
                aria-hidden="true"
              ></i>
            </button>
            <button
              v-if="overdueRowCount"
              type="button"
              data-testid="theater.figure.overdue"
              class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-warning/50 bg-warning/10 px-3 py-1 text-left shadow-1 transition-colors duration-fast ease-standard hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              :aria-expanded="overduePopoverOpen"
              @click="balancePopoverOpen = false; overduePopoverOpen = !overduePopoverOpen"
            >
              <span class="numeric text-sm font-bold text-warning">{{ overdueRowCount }} overdue</span>
              <span v-if="store.overdueMoneyOut.length" class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted normal-case tracking-normal">{{ formatMoney(Math.abs(overdueMoneyOutTotalDollars)) }} owed</span>
            </button>
            <div class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 text-left shadow-1" data-testid="theater.figure.min">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">Window min</span>
              <span class="numeric text-sm font-bold" :class="toneTextClass(headlineFigures.minTone)">{{ headlineFigures.min }}</span>
              <span v-if="headlineFigures.minDate" class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted normal-case tracking-normal">{{ shortDate(headlineFigures.minDate) }}</span>
            </div>
            <div class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 text-left shadow-1" data-testid="theater.figure.days-to-negative">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">To negative</span>
              <span class="numeric text-sm font-bold" :class="toneTextClass(headlineFigures.daysTone)">{{ headlineFigures.daysToNegative }}</span>
            </div>
            <div v-if="lowestBalanceInNext90Days" class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 text-left shadow-1" data-testid="theater.figure.low-90">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">Low 90d</span>
              <span class="numeric text-sm font-bold" :class="lowestBalanceInNext90Days.balanceDollars < 0 ? 'text-negative' : 'text-fg'">{{ formatMoney(Math.round(lowestBalanceInNext90Days.balanceDollars)) }}</span>
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted normal-case tracking-normal">{{ shortDate(lowestBalanceInNext90Days.date) }}</span>
            </div>
            <div class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 text-left shadow-1" data-testid="theater.figure.reserve">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">Reserve</span>
              <span class="numeric text-sm font-bold text-fg">{{ headlineFigures.reserve }}</span>
            </div>
            <div v-if="nextMoneyOut" class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 text-left shadow-1" data-testid="theater.figure.next-out" :title="nextMoneyOut.description">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">Next out</span>
              <span class="numeric text-sm font-bold text-negative">{{ formatSignedMoney(nextMoneyOut.amount_dollars) }}</span>
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted normal-case tracking-normal">{{ shortDate(nextMoneyOut.effective_date) }}</span>
              <DealAttributionTag :txn="nextMoneyOut" class="max-w-[9rem]" />
            </div>
            <div v-if="nextMoneyIn" class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border-ui border-line bg-surface px-3 py-1 text-left shadow-1" data-testid="theater.figure.next-in" :title="nextMoneyIn.description">
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted">Next in</span>
              <span class="numeric text-sm font-bold text-positive">{{ formatSignedMoney(nextMoneyIn.amount_dollars) }}</span>
              <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-fg-muted normal-case tracking-normal">{{ shortDate(nextMoneyIn.effective_date) }}</span>
              <DealAttributionTag :txn="nextMoneyIn" class="max-w-[9rem]" />
            </div>
          </div>

          <!-- Floating action bar -->
          <div data-testid="theater.actions" class="ml-auto flex shrink-0 items-center gap-1 rounded-full border-ui border-line bg-surface/90 p-1 shadow-2">
            <div class="hidden items-center gap-1 md:flex">
              <UiButton data-testid="theater.today" variant="ghost" size="sm" class="gap-1.5 rounded-full" @click="chartRef?.centerOnToday()">
                <i class="pi pi-crosshair text-[10px]" aria-hidden="true"></i> Today
              </UiButton>
              <UiIconButton
                data-testid="theater.mercury-sync"
                :label="store.mercurySyncing ? 'Syncing from Mercury' : 'Re-sync the opening balance from Mercury'"
                :disabled="store.mercurySyncing"
                @click="emit('syncMercury')"
              >
                <i :class="store.mercurySyncing ? 'pi pi-spin pi-spinner' : 'pi pi-sync'" class="text-xs" aria-hidden="true"></i>
              </UiIconButton>
              <UiIconButton data-testid="theater.settings" label="Liquidity settings" @click="emit('openSettings')">
                <i class="pi pi-cog text-xs" aria-hidden="true"></i>
              </UiIconButton>
              <UiIconButton v-if="openCommandPalette" data-testid="theater.search" label="Search or jump to (⌘K)" @click="openCommandPalette()">
                <i class="pi pi-search text-xs" aria-hidden="true"></i>
              </UiIconButton>
              <UiIconButton data-testid="theater.theme" :label="resolvedTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'" @click="toggleTheme()">
                <i :class="resolvedTheme === 'dark' ? 'pi pi-sun' : 'pi pi-moon'" class="text-xs" aria-hidden="true"></i>
              </UiIconButton>
              <UiIconButton
                v-if="browserFullscreenIsSupported"
                data-testid="theater.browser-fullscreen"
                :label="isBrowserFullscreen ? 'Exit browser fullscreen (F)' : 'Browser fullscreen (F)'"
                @click="toggleBrowserFullscreen"
              >
                <i :class="isBrowserFullscreen ? 'pi pi-window-minimize' : 'pi pi-window-maximize'" class="text-xs" aria-hidden="true"></i>
              </UiIconButton>
              <UiIconButton data-testid="theater.shortcuts" label="Keyboard shortcuts (?)" :aria-expanded="shortcutsHelpOpen" @click="shortcutsHelpOpen = !shortcutsHelpOpen">
                <i class="pi pi-question-circle text-xs" aria-hidden="true"></i>
              </UiIconButton>
            </div>
            <UiIconButton
              data-testid="theater.more"
              class="md:hidden"
              label="More actions"
              :aria-expanded="moreActionsMenuOpen"
              @click="moreActionsMenuOpen = !moreActionsMenuOpen"
            >
              <i class="pi pi-ellipsis-h text-xs" aria-hidden="true"></i>
            </UiIconButton>
            <UiButton
              data-testid="theater.legend-toggle"
              aria-label="Legend (L)"
              :variant="legendOpen ? 'secondary' : 'ghost'"
              size="sm"
              class="gap-1.5 rounded-full"
              :aria-expanded="legendOpen"
              @click="legendOpen = !legendOpen"
            >
              <i class="pi pi-list text-[10px]" aria-hidden="true"></i><span class="hidden sm:inline">Legend</span>
            </UiButton>
            <UiButton data-testid="theater.add-flow" aria-label="Add flow" variant="primary" size="sm" class="gap-1.5 rounded-full shadow-glow-primary" @click="emit('addFlow')">
              <i class="pi pi-plus text-[10px]" aria-hidden="true"></i><span class="hidden sm:inline">Add Flow</span>
            </UiButton>
            <UiIconButton data-testid="theater.close" label="Leave the liquidity timeline (Esc)" size="md" @click="emit('leave')">
              <i class="pi pi-times text-sm" aria-hidden="true"></i>
            </UiIconButton>
          </div>

          <!-- Popovers under the top bar -->
          <Transition name="theater-pop">
            <div
              v-if="balancePopoverOpen"
              data-testid="theater.balance-popover"
              class="absolute top-full z-30 mt-2 rounded-card border-ui border-line bg-surface p-4 shadow-3 left-3 w-[min(22rem,calc(100%-1.5rem))]"
            >
              <div class="mb-2 flex items-center justify-between gap-2 text-xs">
                <span class="font-semibold text-fg">Today's balance</span>
                <span v-if="store.mercurySyncing" class="text-fg-muted">syncing…</span>
                <span v-else-if="store.mercuryError" class="text-negative" :title="store.mercuryError">{{ store.mercuryBalance && store.mercuryBalance.workspaces.length > 0 ? 'partial sync' : 'mercury offline' }}</span>
                <span v-else-if="store.mercuryBalance" data-testid="theater.balance-popover.sync" class="text-positive">
                  mercury · {{ store.mercuryBalance.account_count }} account{{ store.mercuryBalance.account_count === 1 ? '' : 's' }} across {{ store.mercuryBalance.workspace_count }} workspace{{ store.mercuryBalance.workspace_count === 1 ? '' : 's' }}<template v-if="mercurySyncedTime"> · synced {{ mercurySyncedTime }}</template>
                </span>
              </div>
              <p v-if="!store.mercuryBalance" class="text-xs text-fg-muted">No Mercury balance yet: the timeline starts from the opening balance in Settings.</p>
              <div v-else class="space-y-2">
                <div v-for="workspace in store.mercuryBalance.workspaces" :key="workspace.workspace" :data-testid="`theater.balance-popover.workspace.${workspace.workspace}`" class="space-y-0.5">
                  <div class="flex items-center justify-between gap-2 text-[11px]">
                    <span class="min-w-0 truncate font-semibold uppercase tracking-wide text-fg">{{ workspace.workspace }}</span>
                    <span class="numeric whitespace-nowrap text-fg">{{ formatMoney(workspace.total_balance_dollars) }}</span>
                  </div>
                  <div v-for="account in workspace.accounts" :key="account.id" :data-testid="`theater.balance-popover.account.${account.id}`" class="flex items-center justify-between gap-2 pl-2 text-[11px] text-fg-muted">
                    <span class="min-w-0 truncate">{{ account.name || account.type || 'Account' }}<template v-if="!account.is_counted_as_cash"> · not counted</template></span>
                    <span class="numeric whitespace-nowrap">{{ formatMoney(account.current_balance_dollars) }}</span>
                  </div>
                </div>
                <div v-for="workspaceError in store.mercuryBalance.workspace_errors" :key="workspaceError.workspace" class="flex justify-between gap-2 text-[11px] text-negative">
                  <span class="font-semibold uppercase">{{ workspaceError.workspace }}</span>
                  <span class="min-w-0 truncate">{{ workspaceError.error }}</span>
                </div>
              </div>
              <UiButton variant="secondary" size="sm" class="mt-3 w-full gap-1.5" :disabled="store.mercurySyncing" @click="emit('syncMercury')">
                <i :class="store.mercurySyncing ? 'pi pi-spin pi-spinner' : 'pi pi-sync'" class="text-[10px]" aria-hidden="true"></i> Re-sync from Mercury
              </UiButton>
            </div>
          </Transition>
          <Transition name="theater-pop">
            <div
              v-if="overduePopoverOpen"
              data-testid="theater.overdue-popover"
              class="absolute top-full z-30 mt-2 rounded-card border-ui border-line bg-surface p-4 shadow-3 left-3 max-h-[70vh] w-[min(40rem,calc(100%-1.5rem))] overflow-y-auto overscroll-contain p-0"
            >
              <OverdueTransactionsStrip
                :overdue-money-out="store.overdueMoneyOut"
                :expected-money-in-not-counted="store.expectedMoneyInNotCounted"
                initially-open
                class="!rounded-none !border-0 !shadow-none"
                @mark-done="(id) => emit('markDone', id)"
                @move-to-date="(id, date) => emit('moveToDate', id, date)"
                @change-amount="(id, dollars) => emit('changeAmount', id, dollars)"
                @bulk-mark-done="(ids) => emit('bulkMarkDone', ids)"
                @bulk-move-to-date="(ids, date) => emit('bulkMoveToDate', ids, date)"
              />
            </div>
          </Transition>
          <Transition name="theater-pop">
            <div v-if="moreActionsMenuOpen" data-testid="theater.more-menu" class="absolute top-full z-30 mt-2 rounded-card border-ui border-line bg-surface p-4 shadow-3 right-3 w-56 p-1">
              <button data-testid="theater.more.today" type="button" class="flex w-full items-center gap-2 rounded-ctl px-3 py-2 text-left text-sm text-fg hover:bg-surface-2 disabled:opacity-50" @click="moreActionsMenuOpen = false; chartRef?.centerOnToday()"><i class="pi pi-crosshair" aria-hidden="true"></i> Today</button>
              <button data-testid="theater.more.mercury-sync" type="button" class="flex w-full items-center gap-2 rounded-ctl px-3 py-2 text-left text-sm text-fg hover:bg-surface-2 disabled:opacity-50" :disabled="store.mercurySyncing" @click="moreActionsMenuOpen = false; emit('syncMercury')"><i class="pi pi-sync" aria-hidden="true"></i> Sync Mercury</button>
              <button data-testid="theater.more.settings" type="button" class="flex w-full items-center gap-2 rounded-ctl px-3 py-2 text-left text-sm text-fg hover:bg-surface-2 disabled:opacity-50" @click="moreActionsMenuOpen = false; emit('openSettings')"><i class="pi pi-cog" aria-hidden="true"></i> Settings</button>
              <button data-testid="theater.more.search" v-if="openCommandPalette" type="button" class="flex w-full items-center gap-2 rounded-ctl px-3 py-2 text-left text-sm text-fg hover:bg-surface-2 disabled:opacity-50" @click="moreActionsMenuOpen = false; openCommandPalette()"><i class="pi pi-search" aria-hidden="true"></i> Search</button>
              <button type="button" class="flex w-full items-center gap-2 rounded-ctl px-3 py-2 text-left text-sm text-fg hover:bg-surface-2 disabled:opacity-50" @click="toggleTheme()"><i :class="resolvedTheme === 'dark' ? 'pi pi-sun' : 'pi pi-moon'" aria-hidden="true"></i> {{ resolvedTheme === 'dark' ? 'Light mode' : 'Dark mode' }}</button>
              <button v-if="browserFullscreenIsSupported" type="button" class="flex w-full items-center gap-2 rounded-ctl px-3 py-2 text-left text-sm text-fg hover:bg-surface-2 disabled:opacity-50" @click="moreActionsMenuOpen = false; toggleBrowserFullscreen()"><i class="pi pi-window-maximize" aria-hidden="true"></i> {{ isBrowserFullscreen ? 'Exit browser fullscreen' : 'Browser fullscreen' }}</button>
            </div>
          </Transition>
          <Transition name="theater-pop">
            <div v-if="shortcutsHelpOpen" data-testid="theater.shortcuts-help" class="absolute top-full z-30 mt-2 rounded-card border-ui border-line bg-surface p-4 shadow-3 right-3 w-64">
              <h2 class="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-fg-muted">Keyboard shortcuts</h2>
              <dl class="space-y-1.5 text-xs">
                <div v-for="shortcut in SHORTCUTS" :key="shortcut.key" class="flex items-center justify-between gap-3">
                  <dt class="text-fg">{{ shortcut.action }}</dt>
                  <dd><kbd class="rounded border-ui border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">{{ shortcut.key }}</kbd></dd>
                </div>
              </dl>
            </div>
          </Transition>
        </div>

        <!-- The stage: the chart edge to edge, the legend and the sheet over it -->
        <div class="relative min-h-0 flex-1" @pointerdown="closePopovers">
          <div class="absolute inset-x-0 bottom-11 top-0">
            <TimelineChart
              ref="chartRef"
              :days="store.series.days"
              :global-min="store.series.globalMin"
              :global-min-dates="store.series.globalMinDates"
              :first-negative-date="store.series.firstNegativeDate"
              :reserve-dollars="store.settings.reserve_dollars"
              :tooltip-follows-pointer="true"
              :highlighted-deal-key="highlightedDealKey"
              @open-day="onOpenDay"
            />
            <div
              v-if="isLoadingForTheFirstTime"
              data-testid="liquidity.loading"
              class="absolute inset-0 z-10 flex items-center justify-center bg-page/60"
            >
              <span class="flex items-center gap-2 text-sm text-fg-muted">
                <i class="pi pi-spin pi-spinner text-primary" aria-hidden="true"></i> Loading liquidity data…
              </span>
            </div>
          </div>

          <Transition name="theater-legend">
            <div v-if="legendOpen" class="pointer-events-none absolute inset-x-3 bottom-14 top-3 z-20 flex flex-col sm:inset-x-auto sm:left-[5.25rem]" @pointerdown.stop>
              <DealLegendPanel
                :imported-deals="store.importedDeals"
                :overdue-money-out="store.overdueMoneyOut"
                :expected-money-in-not-counted="store.expectedMoneyInNotCounted"
                :transactions="store.transactions"
                :recurring-rules="store.recurringRules"
                class="pointer-events-auto max-h-full"
                @close="legendOpen = false"
                @highlight-deal="(dealKey) => (highlightedDealKey = dealKey)"
                @mark-done="(id) => emit('markDone', id)"
                @move-to-date="(id, date) => emit('moveToDate', id, date)"
                @change-amount="(id, dollars) => emit('changeAmount', id, dollars)"
                @review-changes="(deal) => emit('reviewChanges', deal)"
                @remove-deal-from-timeline="(deal) => emit('removeDealFromTimeline', deal)"
                @edit-recurring="(ruleId) => emit('editRecurring', ruleId)"
                @delete-recurring="(ruleId) => emit('deleteRecurring', ruleId)"
                @open-day="onOpenDay"
                @mark-not-done="(id) => emit('markNotDone', id)"
              />
            </div>
          </Transition>

          <DealMilestonesBottomSheet
            :imported-deals="store.importedDeals"
            :open="sheetOpen"
            :milestone-key-being-approved="milestoneKeyBeingApproved"
            @pointerdown.stop
            @toggle="sheetOpen = !sheetOpen"
            @highlight-deal="(dealKey) => (highlightedDealKey = dealKey)"
            @approve-milestone="(deal, milestone) => emit('approveMilestone', deal, milestone)"
            @approve-milestone-on-another-date="(deal, milestone) => emit('changeMilestone', deal, milestone, true)"
            @move-milestone="(deal, milestone) => emit('changeMilestone', deal, milestone, false)"
          />
        </div>

        <DayTransactionsModal
          v-if="dayModalBucket"
          :bucket="dayModalBucket"
          :opening-balance-dollars="dayModalOpeningBalanceDollars"
          :milestones-on-this-day="milestonesOnTheModalDay"
          :can-step-to-previous-day="dayModalIndex > 0"
          :can-step-to-next-day="dayModalIndex < store.series.days.length - 1"
          :done-transactions-of-this-day="doneTransactionsOfTheModalDay"
          @mark-not-done="(id) => emit('markNotDone', id)"
          @close="dayModalDate = null"
          @step-day="stepDayModal"
          @approve-milestone="(deal, milestone) => emit('approveMilestone', deal, milestone)"
          @approve-milestone-on-another-date="(deal, milestone) => emit('changeMilestone', deal, milestone, true)"
          @move-milestone="(deal, milestone) => emit('changeMilestone', deal, milestone, false)"
          @edit-txn="(id) => emit('editTxn', id)"
          @delete-txn="(id) => emit('deleteTxn', id)"
          @add-on-date="(date) => emit('addFlow', date)"
          @mark-done="(id) => emit('markDone', id)"
          @move-to-date="(id, date) => emit('moveToDate', id, date)"
          @change-amount="(id, dollars) => emit('changeAmount', id, dollars)"
        />
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.no-scrollbar {
  scrollbar-width: none;
}
.no-scrollbar::-webkit-scrollbar {
  display: none;
}

/* Only opacity on the root: the chart inside re-measures itself. */
.theater-fade-enter-active,
.theater-fade-leave-active {
  transition: opacity var(--dur-base) var(--ease-standard);
}
.theater-fade-enter-from,
.theater-fade-leave-to {
  opacity: 0;
}

.theater-pop-enter-active,
.theater-pop-leave-active {
  transition:
    opacity var(--dur-fast) var(--ease-standard),
    transform var(--dur-fast) var(--ease-standard);
}
.theater-pop-enter-from,
.theater-pop-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}

.theater-legend-enter-active,
.theater-legend-leave-active {
  transition:
    opacity var(--dur-base) var(--ease-standard),
    transform var(--dur-base) var(--ease-emphasized);
}
.theater-legend-enter-from,
.theater-legend-leave-to {
  opacity: 0;
  transform: translateX(-16px);
}
</style>
