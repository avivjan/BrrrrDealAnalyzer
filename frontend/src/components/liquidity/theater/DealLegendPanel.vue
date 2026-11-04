<script setup lang="ts">
/**
 * The legend of the full-screen timeline (tasks/todo/LiquidityTheaterMode.md, section C): every deal still in
 * the timeline with its color, a red "N overdue" pill, and, on a click, its overdue rows with their one-tap
 * actions, and its Transactions: the deal's key dates and every one of its rows, open and done, month by month
 * (tasks/todo/LiquidityDealTransactionsAndHmlMonthlyInterest.md, B). A done row is greyed out and struck through,
 * with Undo; an open row or a key date opens its day. A deal whose rows are all done sits under "Finished deals",
 * so its done rows stay reachable. Hovering a deal highlights its dots on the chart. A deal can be taken out of the timeline from here
 * (the view confirms first). Manual rows are "Other flows"; the recurring series are listed below.
 *
 * Non-modal on purpose: the chart beside it stays interactive.
 */
import { computed, ref } from 'vue'

import { useInjectedDealAttributionLookup } from '../../../composables/useLiquidityDealAttribution'
import type { ImportedLiquidityDeal, LiquidityRecurringTransaction, LiquidityTransaction } from '../../../types/liquidity'
import { describeRecurrence } from '../../../utils/liquidityEngine'
import { formatSignedMoney } from '../../../utils/money'
import { dealKeyOf, NEUTRAL_DEAL_COLOR_HEX, shortDealAddress } from '../dealColors'
import InlineAmountEditor from '../InlineAmountEditor.vue'
import TransactionRowActions from '../TransactionRowActions.vue'
import { todayISO } from '../../../utils/liquidityEngine'
import { dealTimelineByMonth, monthToOpenFirst, type DealTimelineItem } from './legendRows'

const props = defineProps<{
  importedDeals: ImportedLiquidityDeal[]
  /** Open money out dated before today (counted on today) and open money in dated before today (not counted). */
  overdueMoneyOut: LiquidityTransaction[]
  expectedMoneyInNotCounted: LiquidityTransaction[]
  /** Every one-off row, for the "Other flows" count. */
  transactions: LiquidityTransaction[]
  recurringRules: LiquidityRecurringTransaction[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'highlightDeal', dealKey: string | null): void
  (e: 'markDone', id: string): void
  (e: 'moveToDate', id: string, newEffectiveDate: string): void
  (e: 'changeAmount', id: string, newAmountDollars: number): void
  (e: 'reviewChanges', deal: ImportedLiquidityDeal): void
  (e: 'removeDealFromTimeline', deal: ImportedLiquidityDeal): void
  (e: 'editRecurring', ruleId: string): void
  (e: 'deleteRecurring', ruleId: string): void
  /** Open a day in the day modal (a click on one of a deal's open rows or key dates). */
  (e: 'openDay', date: string): void
  /** Undo a Done: the row is open again. */
  (e: 'markNotDone', id: string): void
}>()

const dealAttributionLookup = useInjectedDealAttributionLookup()

function dealEntryOf(deal: ImportedLiquidityDeal, isFinished: boolean) {
  const dealKey = dealKeyOf(deal.deal_board, deal.deal_id)
  return {
    deal,
    dealKey,
    isFinished,
    dealColorHex: dealAttributionLookup?.value.attributionForDealKey(dealKey)?.dealColorHex ?? NEUTRAL_DEAL_COLOR_HEX,
    shortDealAddress: shortDealAddress(deal.deal_address),
  }
}
type DealEntry = ReturnType<typeof dealEntryOf>

/** A deal with open rows is in the timeline; one whose rows are all done (or removed) is finished. */
const dealsInTheTimeline = computed(() => props.importedDeals.filter(deal => deal.open_row_count > 0).map(deal => dealEntryOf(deal, false)))
const finishedDeals = computed(() => props.importedDeals
  .filter(deal => deal.open_row_count === 0 && deal.done_row_count > 0)
  .map(deal => dealEntryOf(deal, true)))
const finishedDealsShown = ref(false)
/** The deal list as rendered: the deals in the timeline, the "Finished deals" toggle (entry null), then the finished ones when shown. */
const dealListItems = computed<{ key: string; entry: DealEntry | null }[]>(() => [
  ...dealsInTheTimeline.value.map(entry => ({ key: entry.dealKey, entry })),
  ...(finishedDeals.value.length ? [{ key: 'finished-deals-toggle', entry: null }] : []),
  ...(finishedDealsShown.value ? finishedDeals.value.map(entry => ({ key: entry.dealKey, entry })) : []),
])

const overdueRowsOfEveryDeal = computed(() => [
  ...props.overdueMoneyOut.map(txn => ({ txn, isCounted: true })),
  ...props.expectedMoneyInNotCounted.map(txn => ({ txn, isCounted: false })),
])

/** Each deal's overdue rows, live: a Done or a postpone updates the pill at once. */
const overdueRowCountByDealKey = computed(() => {
  const counts = new Map<string, number>()
  for (const { txn } of overdueRowsOfEveryDeal.value) {
    if (!txn.source_deal_board || !txn.source_deal_id) continue
    const dealKey = dealKeyOf(txn.source_deal_board, txn.source_deal_id)
    counts.set(dealKey, (counts.get(dealKey) ?? 0) + 1)
  }
  return counts
})

const expandedDealKey = ref<string | null>(null)
const overdueSectionOpen = ref(true)
const transactionsSectionOpen = ref(false)
const expandedMonthKeys = ref<string[]>([])
function toggleDeal(entry: DealEntry) {
  expandedDealKey.value = expandedDealKey.value === entry.dealKey ? null : entry.dealKey
  overdueSectionOpen.value = true
  expandedMonthKeys.value = []
  // A finished deal has only its transactions to show: open them at once.
  transactionsSectionOpen.value = false
  if (expandedDealKey.value && entry.isFinished) openTransactionsSection()
}

/** The expanded deal's key dates and every one of its rows, open and done, month by month. */
const transactionsOfTheExpandedDealByMonth = computed(() => {
  const deal = props.importedDeals.find(candidate => dealKeyOf(candidate.deal_board, candidate.deal_id) === expandedDealKey.value)
  if (!deal || !expandedDealKey.value) return []
  return dealTimelineByMonth(props.transactions, expandedDealKey.value, deal.key_dates ?? [], deal.milestones)
})
const transactionCountOfTheExpandedDeal = computed(() =>
  transactionsOfTheExpandedDealByMonth.value.reduce((total, month) => total + month.transactionCount, 0))
const doneTransactionCountOfTheExpandedDeal = computed(() =>
  transactionsOfTheExpandedDealByMonth.value.reduce((total, month) => total + month.doneTransactionCount, 0))

function openTransactionsSection() {
  transactionsSectionOpen.value = true
  const monthKey = monthToOpenFirst(transactionsOfTheExpandedDealByMonth.value, todayISO())
  if (monthKey && !expandedMonthKeys.value.length) expandedMonthKeys.value = [monthKey]
}
/** Opening the section shows this month (or the first month with an open row) at once. */
function toggleTransactionsSection() {
  if (transactionsSectionOpen.value) transactionsSectionOpen.value = false
  else openTransactionsSection()
}

function keyDateStateText(item: Extract<DealTimelineItem, { kind: 'key_date' }>): string {
  if (!item.milestoneState) return ''
  if (item.milestoneState.approved_at) return 'done'
  return item.milestoneState.is_overdue ? 'overdue' : 'planned'
}
function shortDoneDate(doneAt: string): string {
  return shortDate(doneAt.slice(0, 10))
}
function toggleMonth(monthKey: string) {
  expandedMonthKeys.value = expandedMonthKeys.value.includes(monthKey)
    ? expandedMonthKeys.value.filter(expandedMonthKey => expandedMonthKey !== monthKey)
    : [...expandedMonthKeys.value, monthKey]
}
const overdueRowsOfTheExpandedDeal = computed(() => overdueRowsOfEveryDeal.value.filter(({ txn }) =>
  !!txn.source_deal_board && !!txn.source_deal_id && dealKeyOf(txn.source_deal_board, txn.source_deal_id) === expandedDealKey.value))

const openManualRowCount = computed(() => props.transactions.filter(txn => !txn.source_deal_id && !txn.done_at).length)

function boardLink(deal: ImportedLiquidityDeal): string {
  return deal.deal_board === 'bought' ? '/bought-deals' : '/my-deals'
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(isoDate: string): string {
  const [, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}`
}
</script>

<template>
  <section
    data-testid="theater.legend"
    aria-labelledby="theater-legend-heading"
    class="flex max-h-full w-full flex-col overflow-hidden rounded-card border-ui border-line bg-surface/95 shadow-3 backdrop-blur-md sm:w-[22rem]"
  >
    <header class="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
      <h2 id="theater-legend-heading" class="text-[11px] font-semibold uppercase tracking-[0.14em] text-fg-muted">Legend</h2>
      <UiIconButton data-testid="theater.legend.close" label="Close the legend" size="sm" @click="emit('close')">
        <i class="pi pi-times text-[10px]" aria-hidden="true"></i>
      </UiIconButton>
    </header>

    <div class="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain p-3">
      <div>
        <h3 class="mb-1.5 px-1 text-[10px] font-semibold uppercase tracking-wider text-fg-muted">Deals</h3>
        <p v-if="!dealsInTheTimeline.length" class="px-1 text-xs text-fg-muted">No deal in the timeline. Import one from its deal card.</p>
        <ul class="space-y-1">
          <template v-for="listItem in dealListItems" :key="listItem.key">
          <li v-if="!listItem.entry">
            <button
              type="button"
              data-testid="theater.legend.finished-deals"
              class="flex w-full items-center gap-2 rounded-ctl px-2 py-1 text-left text-[10px] font-semibold uppercase tracking-wider text-fg-muted hover:text-fg"
              :aria-expanded="finishedDealsShown"
              @click="finishedDealsShown = !finishedDealsShown"
            >
              <i class="pi text-[8px]" :class="finishedDealsShown ? 'pi-chevron-down' : 'pi-chevron-right'" aria-hidden="true"></i>
              Finished deals ({{ finishedDeals.length }})
            </button>
          </li>
          <li
            v-for="entry in (listItem.entry ? [listItem.entry] : [])"
            :key="entry.dealKey"
            data-testid="theater.legend.deal"
            :data-deal-key="entry.dealKey"
            class="rounded-ctl transition-colors duration-fast ease-standard"
            :data-finished="entry.isFinished || undefined"
            :class="[expandedDealKey === entry.dealKey ? 'bg-surface-2' : 'hover:bg-surface-2', entry.isFinished ? 'opacity-80' : '']"
            @mouseenter="emit('highlightDeal', entry.dealKey)"
            @mouseleave="emit('highlightDeal', null)"
          >
            <div class="flex items-center gap-1 pr-1">
              <button
                type="button"
                data-testid="theater.legend.deal.toggle"
                class="flex min-w-0 flex-1 items-center gap-2 rounded-ctl px-2 py-1.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                :aria-expanded="expandedDealKey === entry.dealKey"
                :title="entry.deal.deal_address"
                @click="toggleDeal(entry)"
                @focus="emit('highlightDeal', entry.dealKey)"
                @blur="emit('highlightDeal', null)"
              >
                <span class="h-3 w-3 shrink-0 rounded-full ring-2 ring-surface" :style="{ backgroundColor: entry.dealColorHex }" aria-hidden="true"></span>
                <span class="min-w-0 flex-1 truncate text-sm font-medium text-fg">{{ entry.shortDealAddress }}</span>
                <span
                  v-if="overdueRowCountByDealKey.get(entry.dealKey)"
                  data-testid="theater.legend.deal.overdue"
                  class="shrink-0 rounded-full border-ui border-negative/40 bg-negative/10 px-2 py-px text-[10px] font-bold text-negative"
                >{{ overdueRowCountByDealKey.get(entry.dealKey) }} overdue</span>
                <i class="pi shrink-0 text-[9px] text-fg-muted" :class="expandedDealKey === entry.dealKey ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true"></i>
              </button>
              <UiIconButton
                v-if="entry.deal.liquidity_rows_out_of_date"
                data-testid="theater.legend.deal.review-changes-collapsed"
                size="sm"
                class="text-warning"
                :label="`The deal changed: review ${entry.deal.deal_address}'s liquidity rows`"
                title="The deal changed: review its rows"
                @click="emit('reviewChanges', entry.deal)"
              >
                <i class="pi pi-exclamation-triangle text-[10px]" aria-hidden="true"></i>
              </UiIconButton>
              <RouterLink
                :to="boardLink(entry.deal)"
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-ctl text-fg-muted hover:bg-surface hover:text-primary"
                :aria-label="`Open ${entry.deal.deal_address} on ${entry.deal.deal_board === 'bought' ? 'Bought' : 'My Deals'}`"
                :title="entry.deal.deal_board === 'bought' ? 'Open on Bought' : 'Open on My Deals'"
              >
                <i class="pi pi-external-link text-[10px]" aria-hidden="true"></i>
              </RouterLink>
              <UiIconButton
                v-if="!entry.isFinished"
                data-testid="theater.legend.deal.remove"
                variant="danger"
                size="sm"
                :label="`Remove ${entry.deal.deal_address} from the timeline`"
                title="Remove from the timeline"
                @click="emit('removeDealFromTimeline', entry.deal)"
              >
                <i class="pi pi-trash text-[10px]" aria-hidden="true"></i>
              </UiIconButton>
            </div>

            <!-- The deal's overdue rows, inline: one tap to mark done or postpone. -->
            <div v-if="expandedDealKey === entry.dealKey" data-testid="theater.legend.deal.drawer" class="space-y-2 px-2 pb-2">
              <div class="flex flex-wrap items-center gap-1.5 text-[10px] text-fg-muted">
                <UiBadge tone="neutral" class="px-1.5 py-0 text-[10px]">{{ entry.deal.deal_board === 'bought' ? 'Bought' : 'My Deals' }}</UiBadge>
                <span>{{ entry.deal.open_row_count }} open · {{ entry.deal.done_row_count }} done</span>
                <UiBadge v-if="entry.deal.refi_is_late" data-testid="theater.legend.deal.refi-late" tone="warning" class="px-1.5 py-0 text-[10px]">
                  Refi late · {{ entry.deal.late_refi_row_count }} added row{{ entry.deal.late_refi_row_count === 1 ? '' : 's' }}
                </UiBadge>
                <button
                  v-if="entry.deal.liquidity_rows_out_of_date"
                  type="button"
                  data-testid="theater.legend.deal.review-changes"
                  class="font-semibold text-primary underline"
                  @click="emit('reviewChanges', entry.deal)"
                >Out of date · Review changes</button>
              </div>
              <template v-if="!entry.isFinished">
              <button
                type="button"
                data-testid="theater.legend.deal.overdue-section"
                class="flex w-full items-center justify-between gap-2 rounded-ctl px-1 py-0.5 text-left text-[10px] font-semibold uppercase tracking-wider text-fg-muted hover:text-fg"
                :aria-expanded="overdueSectionOpen"
                @click="overdueSectionOpen = !overdueSectionOpen"
              >
                <span>Overdue ({{ overdueRowsOfTheExpandedDeal.length }})</span>
                <i class="pi text-[9px]" :class="overdueSectionOpen ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true"></i>
              </button>
              <p v-if="overdueSectionOpen && !overdueRowsOfTheExpandedDeal.length" class="px-1 text-xs text-fg-muted">Nothing overdue on this deal.</p>
              <div
                v-for="row in overdueSectionOpen ? overdueRowsOfTheExpandedDeal : []"
                :key="row.txn.id"
                :data-testid="`theater.legend.overdue-row.${row.txn.id}`"
                class="rounded-ctl bg-surface px-3 py-2"
                :class="row.isCounted ? '' : 'opacity-70'"
                :style="{ boxShadow: `inset 3px 0 0 ${entry.dealColorHex}` }"
              >
                <div class="flex items-center gap-2">
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-xs text-fg">{{ row.txn.description }}</div>
                    <div class="text-[10px]" :class="row.isCounted ? 'text-warning' : 'text-fg-muted'">
                      {{ row.isCounted ? `overdue since ${shortDate(row.txn.effective_date)} · counted on today` : `expected ${shortDate(row.txn.effective_date)} · not counted` }}
                    </div>
                  </div>
                  <div class="shrink-0 text-xs font-bold" :class="row.txn.amount_dollars > 0 ? 'text-positive' : 'text-negative'">
                    <InlineAmountEditor :txn="row.txn" @change-amount="(id, dollars) => emit('changeAmount', id, dollars)" />
                  </div>
                </div>
                <TransactionRowActions
                  class="mt-1.5"
                  :txn="row.txn"
                  @mark-done="(id) => emit('markDone', id)"
                  @move-to-date="(id, date) => emit('moveToDate', id, date)"
                />
              </div>

              </template>

              <!--
                Transactions: the deal's key dates and every one of its rows, month by month. A done row is greyed out
                and struck through, with Undo; an open row or a key date opens its day.
              -->
              <button
                type="button"
                data-testid="theater.legend.deal.transactions-section"
                class="flex w-full items-center justify-between gap-2 rounded-ctl px-1 py-0.5 text-left text-[10px] font-semibold uppercase tracking-wider text-fg-muted hover:text-fg"
                :aria-expanded="transactionsSectionOpen"
                @click="toggleTransactionsSection"
              >
                <span>Transactions ({{ transactionCountOfTheExpandedDeal }})<template v-if="doneTransactionCountOfTheExpandedDeal"> · {{ doneTransactionCountOfTheExpandedDeal }} done</template></span>
                <i class="pi text-[9px]" :class="transactionsSectionOpen ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true"></i>
              </button>
              <ul v-if="transactionsSectionOpen" data-testid="theater.legend.deal.transactions" class="space-y-1">
                <li v-for="month in transactionsOfTheExpandedDealByMonth" :key="month.monthKey" data-testid="theater.legend.transactions-month" :data-month="month.monthKey">
                  <button
                    type="button"
                    data-testid="theater.legend.transactions-month.toggle"
                    class="flex w-full items-center gap-2 rounded-ctl bg-surface px-2 py-1 text-left text-[11px] hover:bg-surface-3"
                    :aria-expanded="expandedMonthKeys.includes(month.monthKey)"
                    @click="toggleMonth(month.monthKey)"
                  >
                    <i class="pi text-[8px] text-fg-muted" :class="expandedMonthKeys.includes(month.monthKey) ? 'pi-chevron-down' : 'pi-chevron-right'" aria-hidden="true"></i>
                    <span class="font-semibold text-fg">{{ month.monthLabel }}</span>
                    <span class="flex-1 text-fg-muted">
                      · {{ month.transactionCount }} row{{ month.transactionCount === 1 ? '' : 's' }}<template v-if="month.doneTransactionCount"> · {{ month.doneTransactionCount }} done</template>
                    </span>
                    <span v-if="month.transactionCount" class="numeric font-semibold" :class="month.netDollars < 0 ? 'text-negative' : 'text-positive'">{{ formatSignedMoney(month.netDollars) }}</span>
                  </button>
                  <ul v-if="expandedMonthKeys.includes(month.monthKey)" class="mt-0.5 space-y-px pl-3">
                    <li v-for="item in month.items" :key="item.kind === 'key_date' ? `key-date-${item.keyDate.key}` : item.transaction.id">
                      <!-- A key date: the Cash Needed table's marker, with the milestone's state -->
                      <button
                        v-if="item.kind === 'key_date'"
                        type="button"
                        data-testid="theater.legend.key-date"
                        :data-key-date="item.keyDate.key"
                        class="flex w-full items-center gap-2 rounded-ctl bg-primary/10 px-2 py-0.5 text-left text-[10px] font-semibold uppercase tracking-wider text-primary hover:bg-primary/15"
                        :title="`Open ${shortDate(item.date)}`"
                        @click="emit('openDay', item.date)"
                      >
                        <span class="w-11 shrink-0 tabular-nums">{{ shortDate(item.date) }}</span>
                        <i
                          :class="item.milestoneState?.approved_at ? 'pi pi-check-circle text-positive' : item.milestoneState?.is_overdue ? 'pi pi-exclamation-circle text-negative' : 'pi pi-flag'"
                          class="shrink-0 text-[9px]"
                          aria-hidden="true"
                        ></i>
                        <span class="min-w-0 flex-1 truncate">{{ item.keyDate.description }}</span>
                        <span v-if="keyDateStateText(item)" class="shrink-0 normal-case tracking-normal" :class="item.milestoneState?.approved_at ? 'text-positive' : item.milestoneState?.is_overdue ? 'text-negative' : 'text-fg-muted'">{{ keyDateStateText(item) }}</span>
                      </button>
                      <!-- A done row: greyed out, struck through, with Undo -->
                      <div
                        v-else-if="item.transaction.done_at"
                        :data-testid="`theater.legend.transaction.${item.transaction.id}`"
                        data-done="true"
                        class="flex w-full items-center gap-2 rounded-ctl px-2 py-0.5 text-[11px] opacity-60"
                      >
                        <span class="w-11 shrink-0 tabular-nums text-fg-muted line-through">{{ shortDate(item.transaction.effective_date) }}</span>
                        <span class="min-w-0 flex-1 truncate text-fg-muted line-through" :title="`${item.transaction.description} · done ${shortDoneDate(item.transaction.done_at)}`">{{ item.transaction.description }}</span>
                        <span class="numeric shrink-0 text-fg-muted line-through">{{ formatSignedMoney(item.transaction.amount_dollars) }}</span>
                        <button
                          type="button"
                          :data-testid="`theater.legend.transaction.${item.transaction.id}.undo`"
                          class="shrink-0 rounded px-1.5 py-px text-[10px] font-semibold text-primary no-underline hover:bg-primary/10"
                          :aria-label="`Undo done: ${item.transaction.description}`"
                          :title="`Done ${shortDoneDate(item.transaction.done_at)}: undo`"
                          @click="emit('markNotDone', item.transaction.id)"
                        >Undo</button>
                      </div>
                      <!-- An open row: a click opens its day -->
                      <button
                        v-else
                        type="button"
                        :data-testid="`theater.legend.transaction.${item.transaction.id}`"
                        data-done="false"
                        class="flex w-full items-center gap-2 rounded-ctl px-2 py-0.5 text-left text-[11px] hover:bg-surface"
                        :title="`Open ${shortDate(item.transaction.effective_date)}`"
                        @click="emit('openDay', item.transaction.effective_date)"
                      >
                        <span class="w-11 shrink-0 tabular-nums text-fg-muted">{{ shortDate(item.transaction.effective_date) }}</span>
                        <i v-if="item.transaction.created_because_refi_is_late" class="pi pi-clock shrink-0 text-[9px] text-warning" title="Added while the refi is late" aria-hidden="true"></i>
                        <i v-if="item.transaction.no_longer_in_the_deal" class="pi pi-info-circle shrink-0 text-[9px] text-fg-muted" title="No longer in the deal: kept because you changed it" aria-hidden="true"></i>
                        <span class="min-w-0 flex-1 truncate text-fg">{{ item.transaction.description }}</span>
                        <span class="numeric shrink-0" :class="item.transaction.amount_dollars < 0 ? 'text-negative' : 'text-positive'">{{ formatSignedMoney(item.transaction.amount_dollars) }}</span>
                      </button>
                    </li>
                  </ul>
                </li>
              </ul>
            </div>
          </li>
          </template>
          <li v-if="openManualRowCount" data-testid="theater.legend.other-flows" class="flex items-center gap-2 px-2 py-1.5">
            <span class="h-3 w-3 shrink-0 rounded-full ring-2 ring-surface" :style="{ backgroundColor: NEUTRAL_DEAL_COLOR_HEX }" aria-hidden="true"></span>
            <span class="flex-1 text-sm text-fg-muted">Other flows</span>
            <span class="text-[10px] text-fg-muted">{{ openManualRowCount }} open</span>
          </li>
        </ul>
      </div>

      <div v-if="recurringRules.length">
        <h3 class="mb-1.5 flex items-center gap-1.5 px-1 text-[10px] font-semibold uppercase tracking-wider text-fg-muted">
          <i class="pi pi-refresh text-[9px] text-primary" aria-hidden="true"></i> Recurring
        </h3>
        <ul class="space-y-1">
          <li
            v-for="rule in recurringRules"
            :key="rule.id"
            :data-testid="`theater.legend.recurring.${rule.id}`"
            class="group flex items-center gap-2 rounded-ctl px-2 py-1.5 hover:bg-surface-2"
          >
            <div class="min-w-0 flex-1">
              <div class="truncate text-xs text-fg">{{ rule.description }}</div>
              <div class="truncate text-[10px] text-fg-muted">{{ describeRecurrence(rule) }}</div>
            </div>
            <span class="numeric shrink-0 text-xs font-bold" :class="rule.amount_dollars > 0 ? 'text-positive' : 'text-negative'">{{ formatSignedMoney(rule.amount_dollars) }}</span>
            <span class="flex shrink-0 gap-1 opacity-0 transition-opacity duration-fast ease-standard focus-within:opacity-100 group-hover:opacity-100 touch:opacity-100">
              <UiIconButton :data-testid="`theater.legend.recurring.${rule.id}.edit`" label="Edit series" size="sm" @click="emit('editRecurring', rule.id)">
                <i class="pi pi-pencil text-[9px]" aria-hidden="true"></i>
              </UiIconButton>
              <UiIconButton :data-testid="`theater.legend.recurring.${rule.id}.delete`" label="Delete series" variant="danger" size="sm" @click="emit('deleteRecurring', rule.id)">
                <i class="pi pi-trash text-[9px]" aria-hidden="true"></i>
              </UiIconButton>
            </span>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
