<script setup lang="ts">
/**
 * The one- or two-tap actions on a one-off liquidity row: ✓ Done, the postpone chips
 * (+1 day, +1 week, next 1st) and a date picker. A recurring occurrence has none: it is
 * edited through its rule. The chips count from today for an overdue row (moving it
 * relative to its past date would leave it overdue).
 */
import { computed, useId } from 'vue'

import type { LiquidityTransaction } from '../../types/liquidity'
import { addDays, firstOfNextMonth, todayISO } from '../../utils/liquidityEngine'

const props = defineProps<{ txn: LiquidityTransaction }>()

const emit = defineEmits<{
  (e: 'markDone', id: string): void
  (e: 'moveToDate', id: string, newEffectiveDate: string): void
}>()

const datePickerId = useId()
const plannedDate = computed(() => props.txn.overdue_since_date ?? props.txn.effective_date)
/** The date the chips count from: the row's own date, or today when that has passed. */
const postponeFromDate = computed(() => {
  const today = todayISO()
  return plannedDate.value > today ? plannedDate.value : today
})
const postponeChips = computed(() => [
  { key: 'day', label: '+1 day', date: addDays(postponeFromDate.value, 1) },
  { key: 'week', label: '+1 week', date: addDays(postponeFromDate.value, 7) },
  { key: 'first', label: 'Next 1st', date: firstOfNextMonth(postponeFromDate.value) },
])

function onPickDate(event: Event) {
  const value = (event.target as HTMLInputElement).value
  if (value) emit('moveToDate', props.txn.id, value)
}
</script>

<template>
  <div v-if="!txn.recurring_rule_id" :data-testid="`rowactions.${txn.id}`" class="flex flex-wrap items-center gap-1.5">
    <UiButton
      :data-testid="`rowactions.${txn.id}.done`"
      variant="secondary"
      size="sm"
      class="min-h-8 touch:min-h-11 gap-1 text-positive"
      :title="'Done: the money moved, or the hold was released'"
      @click="emit('markDone', txn.id)"
    >
      <i class="pi pi-check text-[10px]" aria-hidden="true"></i> Done
    </UiButton>
    <UiButton
      v-for="chip in postponeChips"
      :key="chip.key"
      :data-testid="`rowactions.${txn.id}.postpone.${chip.key}`"
      variant="ghost"
      size="sm"
      class="min-h-8 touch:min-h-11 text-fg-muted"
      :title="`Move to ${chip.date}`"
      @click="emit('moveToDate', txn.id, chip.date)"
    >
      {{ chip.label }}
    </UiButton>
    <label :for="datePickerId" class="sr-only">Move {{ txn.description }} to a date</label>
    <input
      :id="datePickerId"
      :data-testid="`rowactions.${txn.id}.date`"
      type="date"
      class="ui-input h-8 w-[9.5rem] touch:h-11 text-xs"
      :min="todayISO()"
      @change="onPickDate"
    />
  </div>
</template>
