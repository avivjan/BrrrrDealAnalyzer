<script setup lang="ts">
/**
 * The before -> after list of a deal's liquidity rows: what an import, a re-sync or a milestone change would do,
 * shown before anything changes. Rows whose date or amount you changed by hand keep your value; the list says what
 * the deal now says and one tap ("Use ...") takes the deal's value instead (`useDealValueFor`, v-model).
 * Unchanged rows are folded under one line.
 */
import { computed, ref } from 'vue'

import type { DealCashRowChange, UseDealValueForField } from '../../types/liquidity'
import { formatSignedMoney } from '../../utils/money'
import UiBadge from '../ui/UiBadge.vue'

const props = defineProps<{
  changes: DealCashRowChange[]
  useDealValueFor: UseDealValueForField[]
}>()

const emit = defineEmits<{
  (e: 'update:useDealValueFor', value: UseDealValueForField[]): void
}>()

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(isoDate: string | null): string {
  if (!isoDate) return ''
  const [year, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}, ${year}`
}

const CHANGE_KIND_LABELS: Record<DealCashRowChange['change_kind'], { label: string; tone: 'positive' | 'negative' | 'warning' | 'neutral' | 'info' }> = {
  added: { label: 'Added', tone: 'positive' },
  updated: { label: 'Changed', tone: 'info' },
  removed: { label: 'Removed', tone: 'negative' },
  unchanged: { label: 'Unchanged', tone: 'neutral' },
  kept_done: { label: 'Done, kept', tone: 'neutral' },
  kept_no_longer_in_the_deal: { label: 'Kept: you changed it', tone: 'warning' },
}

const showUnchangedRows = ref(false)
const changedRows = computed(() => props.changes.filter(change =>
  change.change_kind !== 'unchanged' || change.deal_date_not_applied_because_you_changed_it || change.deal_amount_dollars_not_applied_because_you_changed_it !== null))
const unchangedRows = computed(() => props.changes.filter(change => !changedRows.value.includes(change)))

function takesTheDealsValue(change: DealCashRowChange, field: 'date' | 'amount'): boolean {
  return props.useDealValueFor.some(choice => choice.transaction_id === change.transaction_id && choice.field === field)
}

function toggleTheDealsValue(change: DealCashRowChange, field: 'date' | 'amount') {
  if (!change.transaction_id) return
  const withoutThisChoice = props.useDealValueFor.filter(choice => !(choice.transaction_id === change.transaction_id && choice.field === field))
  emit('update:useDealValueFor', takesTheDealsValue(change, field)
    ? withoutThisChoice
    : [...withoutThisChoice, { transaction_id: change.transaction_id, field }])
}

function rowKey(change: DealCashRowChange): string {
  return `${change.item_key}-${change.occurrence_number}`
}
</script>

<template>
  <div data-testid="deal-cash-row-changes" class="flex flex-col gap-1.5">
    <p v-if="changedRows.length === 0" class="text-sm text-fg-muted">No row changes.</p>
    <div
      v-for="change in changedRows"
      :key="rowKey(change)"
      data-testid="deal-cash-row-change"
      :data-change-kind="change.change_kind"
      class="rounded-ctl border-ui border-line px-3 py-2 text-sm"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UiBadge :tone="CHANGE_KIND_LABELS[change.change_kind].tone">{{ CHANGE_KIND_LABELS[change.change_kind].label }}</UiBadge>
        <UiBadge v-if="change.created_because_refi_is_late" tone="warning">Refi late</UiBadge>
        <span class="font-medium text-fg">{{ change.description }}</span>
      </div>
      <div class="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 tabular-nums text-fg-muted">
        <span data-part="date">
          <template v-if="change.date_before && change.date_after && change.date_before !== change.date_after">
            {{ shortDate(change.date_before) }} → <strong class="text-fg">{{ shortDate(change.date_after) }}</strong>
          </template>
          <template v-else>{{ shortDate(change.date_after ?? change.date_before) }}</template>
        </span>
        <span data-part="amount">
          <template v-if="change.amount_dollars_before !== null && change.amount_dollars_after !== null && change.amount_dollars_before !== change.amount_dollars_after">
            {{ formatSignedMoney(change.amount_dollars_before) }} → <strong class="text-fg">{{ formatSignedMoney(change.amount_dollars_after) }}</strong>
          </template>
          <template v-else>{{ formatSignedMoney((change.amount_dollars_after ?? change.amount_dollars_before) ?? 0) }}</template>
        </span>
      </div>
      <div v-if="change.deal_date_not_applied_because_you_changed_it" data-testid="deal-cash-row-date-conflict" class="mt-1 flex flex-wrap items-center gap-2 text-xs text-warning">
        <span>Kept your date {{ shortDate(change.date_before) }} (the deal now says {{ shortDate(change.deal_date_not_applied_because_you_changed_it) }})</span>
        <button type="button" class="font-semibold underline" @click="toggleTheDealsValue(change, 'date')">
          {{ takesTheDealsValue(change, 'date') ? 'Keep my date' : `Use ${shortDate(change.deal_date_not_applied_because_you_changed_it)}` }}
        </button>
      </div>
      <div v-if="change.deal_amount_dollars_not_applied_because_you_changed_it !== null" data-testid="deal-cash-row-amount-conflict" class="mt-1 flex flex-wrap items-center gap-2 text-xs text-warning">
        <span>Kept your {{ formatSignedMoney(change.amount_dollars_before ?? 0) }} (the deal now says {{ formatSignedMoney(change.deal_amount_dollars_not_applied_because_you_changed_it) }})</span>
        <button type="button" class="font-semibold underline" @click="toggleTheDealsValue(change, 'amount')">
          {{ takesTheDealsValue(change, 'amount') ? 'Keep my amount' : `Use ${formatSignedMoney(change.deal_amount_dollars_not_applied_because_you_changed_it)}` }}
        </button>
      </div>
    </div>
    <button
      v-if="unchangedRows.length > 0"
      type="button"
      data-testid="deal-cash-row-changes.toggle-unchanged"
      class="self-start text-xs font-semibold text-fg-muted underline"
      @click="showUnchangedRows = !showUnchangedRows"
    >
      {{ showUnchangedRows ? 'Hide' : 'Show' }} {{ unchangedRows.length }} unchanged row{{ unchangedRows.length === 1 ? '' : 's' }}
    </button>
    <template v-if="showUnchangedRows">
      <div v-for="change in unchangedRows" :key="rowKey(change)" class="flex justify-between gap-3 px-3 text-xs text-fg-muted">
        <span>{{ shortDate(change.date_after) }} · {{ change.description }}</span>
        <span class="tabular-nums">{{ formatSignedMoney(change.amount_dollars_after ?? 0) }}</span>
      </div>
    </template>
  </div>
</template>
