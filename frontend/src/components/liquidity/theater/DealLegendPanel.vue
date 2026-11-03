<script setup lang="ts">
/**
 * The legend of the full-screen timeline (tasks/todo/LiquidityTheaterMode.md, section C): every deal still in
 * the timeline with its color, a red "N overdue" pill, and, on a click, its overdue rows with their one-tap
 * actions. Hovering a deal highlights its dots on the chart. A deal can be taken out of the timeline from here
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
}>()

const dealAttributionLookup = useInjectedDealAttributionLookup()

/** A deal whose open rows were all removed or done is out of the timeline (its done rows keep their color). */
const dealsInTheTimeline = computed(() => props.importedDeals
  .filter(deal => deal.open_row_count > 0)
  .map(deal => {
    const dealKey = dealKeyOf(deal.deal_board, deal.deal_id)
    return {
      deal,
      dealKey,
      dealColorHex: dealAttributionLookup?.value.attributionForDealKey(dealKey)?.dealColorHex ?? NEUTRAL_DEAL_COLOR_HEX,
      shortDealAddress: shortDealAddress(deal.deal_address),
    }
  }))

const overdueRowsOfEveryDeal = computed(() => [
  ...props.overdueMoneyOut.map(txn => ({ txn, isCounted: true })),
  ...props.expectedMoneyInNotCounted.map(txn => ({ txn, isCounted: false })),
])

const expandedDealKey = ref<string | null>(null)
function toggleDeal(dealKey: string) {
  expandedDealKey.value = expandedDealKey.value === dealKey ? null : dealKey
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
          <li
            v-for="entry in dealsInTheTimeline"
            :key="entry.dealKey"
            data-testid="theater.legend.deal"
            :data-deal-key="entry.dealKey"
            class="rounded-ctl transition-colors duration-fast ease-standard"
            :class="expandedDealKey === entry.dealKey ? 'bg-surface-2' : 'hover:bg-surface-2'"
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
                @click="toggleDeal(entry.dealKey)"
                @focus="emit('highlightDeal', entry.dealKey)"
                @blur="emit('highlightDeal', null)"
              >
                <span class="h-3 w-3 shrink-0 rounded-full ring-2 ring-surface" :style="{ backgroundColor: entry.dealColorHex }" aria-hidden="true"></span>
                <span class="min-w-0 flex-1 truncate text-sm font-medium text-fg">{{ entry.shortDealAddress }}</span>
                <span
                  v-if="entry.deal.overdue_open_row_count"
                  data-testid="theater.legend.deal.overdue"
                  class="shrink-0 rounded-full border-ui border-negative/40 bg-negative/10 px-2 py-px text-[10px] font-bold text-negative"
                >{{ entry.deal.overdue_open_row_count }} overdue</span>
                <i class="pi shrink-0 text-[9px] text-fg-muted" :class="expandedDealKey === entry.dealKey ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true"></i>
              </button>
              <RouterLink
                :to="boardLink(entry.deal)"
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-ctl text-fg-muted hover:bg-surface hover:text-primary"
                :aria-label="`Open ${entry.deal.deal_address} on ${entry.deal.deal_board === 'bought' ? 'Bought' : 'My Deals'}`"
                :title="entry.deal.deal_board === 'bought' ? 'Open on Bought' : 'Open on My Deals'"
              >
                <i class="pi pi-external-link text-[10px]" aria-hidden="true"></i>
              </RouterLink>
              <UiIconButton
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
                <UiBadge v-if="entry.deal.refi_is_late" tone="warning" class="px-1.5 py-0 text-[10px]">Refi late</UiBadge>
                <button
                  v-if="entry.deal.liquidity_rows_out_of_date"
                  type="button"
                  data-testid="theater.legend.deal.review-changes"
                  class="font-semibold text-primary underline"
                  @click="emit('reviewChanges', entry.deal)"
                >Out of date · Review changes</button>
              </div>
              <p v-if="!overdueRowsOfTheExpandedDeal.length" class="text-xs text-fg-muted">Nothing overdue on this deal.</p>
              <div
                v-for="row in overdueRowsOfTheExpandedDeal"
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
            </div>
          </li>
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
