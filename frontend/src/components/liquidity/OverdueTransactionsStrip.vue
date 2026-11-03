<script setup lang="ts">
/**
 * What is still owed or expected from the past, above the chart: overdue money out (counted
 * on today, so today's balance already reflects it) and overdue money in (shown, but not counted
 * until it gets a new date or is marked done). Each row carries the row actions; ticking rows
 * opens a bulk bar to mark them done or postpone them together.
 */
import { computed, ref, watch } from 'vue'

import type { LiquidityTransaction } from '../../types/liquidity'
import { addDays, firstOfNextMonth, todayISO } from '../../utils/liquidityEngine'
import { formatMoney } from '../../utils/money'
import { dealAccentStyleForTransaction, useInjectedDealAttributionLookup } from '../../composables/useLiquidityDealAttribution'
import DealAttributionTag from './DealAttributionTag.vue'
import InlineAmountEditor from './InlineAmountEditor.vue'
import TransactionRowActions from './TransactionRowActions.vue'

const props = defineProps<{
  overdueMoneyOut: LiquidityTransaction[]
  expectedMoneyInNotCounted: LiquidityTransaction[]
  /** Start with the rows shown (the theater's overdue popover, opened on purpose). */
  initiallyOpen?: boolean
}>()

const emit = defineEmits<{
  (e: 'markDone', id: string): void
  (e: 'moveToDate', id: string, newEffectiveDate: string): void
  (e: 'changeAmount', id: string, newAmountDollars: number): void
  (e: 'bulkMarkDone', ids: string[]): void
  (e: 'bulkMoveToDate', ids: string[], newEffectiveDate: string): void
}>()

/** Each row's deal (a tag and a left accent in its color), when the view provides the lookup. */
const dealAttributionLookup = useInjectedDealAttributionLookup()

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(iso: string): string {
  const [, month, day] = iso.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}`
}

const rows = computed(() => [
  ...props.overdueMoneyOut.map((txn) => ({ txn, isCounted: true })),
  ...props.expectedMoneyInNotCounted.map((txn) => ({ txn, isCounted: false })),
])
const overdueMoneyOutTotalDollars = computed(() => props.overdueMoneyOut.reduce((total, txn) => total + txn.amount_dollars, 0))
const isOpen = ref(!!props.initiallyOpen)

const selectedIds = ref<string[]>([])
// A row that left the strip (done, or moved to a date ahead) is no longer selectable.
watch(rows, (current) => {
  const present = new Set(current.map((row) => row.txn.id))
  selectedIds.value = selectedIds.value.filter((id) => present.has(id))
})
const bulkDates = computed(() => {
  const today = todayISO()
  return [
    { key: 'day', label: '+1 day', date: addDays(today, 1) },
    { key: 'week', label: '+1 week', date: addDays(today, 7) },
    { key: 'first', label: 'Next 1st', date: firstOfNextMonth(today) },
  ]
})
function bulkMoveTo(date: string) {
  emit('bulkMoveToDate', [...selectedIds.value], date)
  selectedIds.value = []
}
function bulkMarkDone() {
  emit('bulkMarkDone', [...selectedIds.value])
  selectedIds.value = []
}
</script>

<template>
  <section v-if="rows.length" data-testid="overdue.root" class="rounded-card border-ui border-warning/50 bg-warning/5 p-3 shadow-1">
    <button
      type="button"
      data-testid="overdue.toggle"
      class="flex w-full items-center justify-between gap-3 text-left"
      :aria-expanded="isOpen"
      @click="isOpen = !isOpen"
    >
      <span class="flex flex-wrap items-center gap-2">
        <UiBadge tone="warning" data-testid="overdue.count">{{ rows.length }} overdue</UiBadge>
        <span v-if="overdueMoneyOut.length" class="text-sm text-fg">
          {{ formatMoney(Math.abs(overdueMoneyOutTotalDollars)) }} still owed, counted on today
        </span>
        <span v-if="expectedMoneyInNotCounted.length" class="text-sm text-fg-muted">
          · {{ expectedMoneyInNotCounted.length }} expected in, not counted
        </span>
      </span>
      <i class="pi text-xs text-fg-muted" :class="isOpen ? 'pi-chevron-up' : 'pi-chevron-down'" aria-hidden="true"></i>
    </button>

    <div v-if="isOpen" class="mt-3 space-y-2">
      <div v-if="selectedIds.length" data-testid="overdue.bulk" class="flex flex-wrap items-center gap-1.5 rounded-ctl bg-surface-2 px-3 py-2">
        <span class="mr-1 text-xs text-fg-muted">{{ selectedIds.length }} selected</span>
        <UiButton data-testid="overdue.bulk.done" variant="secondary" size="sm" class="min-h-8 touch:min-h-11 text-positive" @click="bulkMarkDone">
          <i class="pi pi-check text-[10px]" aria-hidden="true"></i> Done
        </UiButton>
        <UiButton
          v-for="chip in bulkDates"
          :key="chip.key"
          :data-testid="`overdue.bulk.postpone.${chip.key}`"
          variant="ghost"
          size="sm"
          class="min-h-8 touch:min-h-11 text-fg-muted"
          @click="bulkMoveTo(chip.date)"
        >
          {{ chip.label }}
        </UiButton>
      </div>

      <div
        v-for="row in rows"
        :key="row.txn.id"
        :data-testid="`overdue.row.${row.txn.id}`"
        class="rounded-ctl bg-surface px-3 py-2"
        :class="row.isCounted ? '' : 'opacity-70'"
        :style="dealAccentStyleForTransaction(dealAttributionLookup, row.txn)"
      >
        <div class="flex items-center gap-2">
          <input
            v-model="selectedIds"
            :data-testid="`overdue.row.${row.txn.id}.select`"
            :aria-label="`Select ${row.txn.description}`"
            type="checkbox"
            class="h-4 w-4 shrink-0 accent-primary"
            :value="row.txn.id"
          />
          <div class="min-w-0 flex-1">
            <div class="flex min-w-0 items-center gap-2">
              <span class="truncate text-sm text-fg">{{ row.txn.description }}</span>
              <DealAttributionTag :txn="row.txn" class="shrink-0" />
            </div>
            <div class="text-xs" :class="row.isCounted ? 'text-warning' : 'text-fg-muted'">
              <template v-if="row.isCounted">overdue since {{ shortDate(row.txn.effective_date) }} · counted on today</template>
              <template v-else>expected {{ shortDate(row.txn.effective_date) }} · not counted until you give it a new date</template>
            </div>
          </div>
          <div class="shrink-0 text-sm font-bold" :class="row.txn.amount_dollars > 0 ? 'text-positive' : 'text-negative'">
            <InlineAmountEditor :txn="row.txn" @change-amount="(id, dollars) => emit('changeAmount', id, dollars)" />
          </div>
        </div>
        <TransactionRowActions
          class="mt-2"
          :txn="row.txn"
          @mark-done="(id) => emit('markDone', id)"
          @move-to-date="(id, date) => emit('moveToDate', id, date)"
        />
      </div>
    </div>
  </section>
</template>
