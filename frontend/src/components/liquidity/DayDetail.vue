<script setup lang="ts">
import type { DayBucket } from '../../types/liquidity'
import { formatMoney, formatSignedMoney } from '../../utils/money'
import { dealAccentStyleForTransaction, useInjectedDealAttributionLookup } from '../../composables/useLiquidityDealAttribution'
import DealAttributionTag from './DealAttributionTag.vue'
import InlineAmountEditor from './InlineAmountEditor.vue'
import TransactionRowActions from './TransactionRowActions.vue'

defineProps<{
  bucket: DayBucket | null
  /** The caller already shows the date, the net and the end-of-day balance (the theater's day modal). */
  hideDayHeading?: boolean
  /** A link opened the day on this row: it is outlined. */
  highlightedTransactionId?: string | null
}>()

const emit = defineEmits<{
  (e: 'editTxn', id: string): void
  (e: 'deleteTxn', id: string): void
  (e: 'addOnDate', date: string): void
  (e: 'markDone', id: string): void
  (e: 'moveToDate', id: string, newEffectiveDate: string): void
  (e: 'changeAmount', id: string, newAmountDollars: number): void
}>()

/** Each row's deal (a tag and a left accent in its color), when the view provides the lookup. */
const dealAttributionLookup = useInjectedDealAttributionLookup()

function formatDate(iso: string): string {
  const parts = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return (months[parseInt(parts[1] ?? '0') - 1] ?? '') + ' ' + parseInt(parts[2] ?? '0') + ', ' + (parts[0] ?? '')
}
</script>

<template>
  <div v-if="bucket" data-testid="daydetail.root" class="rounded-card border-ui border-line bg-surface p-4 shadow-1">
    <div class="mb-3 flex items-center justify-between gap-2">
      <h3 v-if="!hideDayHeading" class="min-w-0 truncate font-display text-base font-semibold tracking-display text-fg">{{ formatDate(bucket.date) }}</h3>
      <h3 v-else class="text-[10px] font-semibold uppercase tracking-wider text-fg-muted">Transactions ({{ bucket.transactions.length }})</h3>
      <UiButton
        data-testid="daydetail.add"
        variant="ghost"
        size="sm"
        class="min-h-9 touch:min-h-11 shrink-0 text-primary hover:text-primary-hover"
        @click="emit('addOnDate', bucket.date)"
      >
        + Add flow
      </UiButton>
    </div>

    <div v-if="!hideDayHeading" class="mb-3 flex gap-4 text-xs">
      <div>
        <span class="text-fg-muted">Net: </span>
        <span class="numeric font-semibold" :class="bucket.net_dollars > 0 ? 'text-positive' : bucket.net_dollars < 0 ? 'text-negative' : 'text-fg-muted'">
          {{ formatSignedMoney(bucket.net_dollars) }}
        </span>
      </div>
      <div>
        <span class="text-fg-muted">EOD: </span>
        <span :class="bucket.balance_dollars < 0 ? 'text-negative' : 'text-primary'" class="numeric font-bold">
          {{ formatMoney(bucket.balance_dollars) }}
        </span>
      </div>
    </div>

    <div v-if="bucket.transactions.length === 0" data-testid="daydetail.empty" class="py-2 text-xs text-fg-muted">
      No transactions on this date.
    </div>

    <!-- Rows enter, leave and reflow (id-keyed); the group is inert under reduced motion. -->
    <UiTransitionGroup v-else preset="listItem" tag="div" class="space-y-1.5">
      <div
        v-for="txn in bucket.transactions"
        :key="txn.id"
        :data-testid="`daydetail.txn.${txn.id}`"
        class="group rounded-ctl bg-surface-2 px-3 py-2"
        :class="[txn.recurring_rule_id ? 'ring-1 ring-inset ring-primary/30' : '', highlightedTransactionId === txn.id ? 'ring-2 ring-primary' : '']"
        :data-highlighted="highlightedTransactionId === txn.id || undefined"
        :style="dealAccentStyleForTransaction(dealAttributionLookup, txn)"
      >
        <div class="flex items-center gap-2">
        <div class="h-1.5 w-1.5 shrink-0 rounded-full"
          :class="txn.amount_dollars > 0 ? 'bg-positive' : 'bg-negative'"
        />
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <div class="min-w-0 break-words text-xs text-fg line-clamp-2">{{ txn.description }}</div>
            <DealAttributionTag :txn="txn" links-to-the-deal class="shrink-0" />
            <UiBadge
              v-if="txn.recurring_rule_id"
              tone="primary"
              class="shrink-0 gap-0.5 px-1 py-0.5 text-[9px]"
              title="Projected from a recurring rule. Edit/delete affects the whole series."
            >
              <i class="pi pi-refresh text-[8px]" aria-hidden="true"></i>
              recurring
            </UiBadge>
            <UiBadge
              v-if="txn.overdue_since_date"
              :data-testid="`daydetail.txn.${txn.id}.overdue`"
              tone="warning"
              class="shrink-0 px-1 py-0.5 text-[9px]"
              title="Not marked done yet: counted on today"
            >
              overdue since {{ formatDate(txn.overdue_since_date) }}
            </UiBadge>
          </div>
        </div>
        <div class="shrink-0 text-xs font-bold numeric"
          :class="txn.amount_dollars > 0 ? 'text-positive' : 'text-negative'"
        >
          <InlineAmountEditor :txn="txn" @change-amount="(id, dollars) => emit('changeAmount', id, dollars)" />
        </div>
        <div class="flex shrink-0 gap-2 opacity-0 transition-opacity duration-fast ease-standard focus-within:opacity-100 group-hover:opacity-100 touch:opacity-100">
          <UiIconButton
            :data-testid="`daydetail.txn.${txn.id}.edit`"
            :title="txn.recurring_rule_id ? 'Edit recurring series' : 'Edit'"
            :label="txn.recurring_rule_id ? 'Edit recurring series' : 'Edit'"
            @click="emit('editTxn', txn.id)"
          >
            <i class="pi pi-pencil text-[10px]" aria-hidden="true"></i>
          </UiIconButton>
          <UiIconButton
            :data-testid="`daydetail.txn.${txn.id}.delete`"
            variant="danger"
            :title="txn.recurring_rule_id ? 'Delete recurring series' : 'Delete'"
            :label="txn.recurring_rule_id ? 'Delete recurring series' : 'Delete'"
            @click="emit('deleteTxn', txn.id)"
          >
            <i class="pi pi-trash text-[10px]" aria-hidden="true"></i>
          </UiIconButton>
        </div>
        </div>
        <TransactionRowActions
          class="mt-1.5 pl-3.5"
          :txn="txn"
          @mark-done="(id) => emit('markDone', id)"
          @move-to-date="(id, date) => emit('moveToDate', id, date)"
        />
      </div>
    </UiTransitionGroup>
  </div>
</template>
