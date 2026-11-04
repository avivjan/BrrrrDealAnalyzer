<script setup lang="ts">
/**
 * A day of the full-screen timeline, in full (tasks/todo/LiquidityTheaterMode.md, section E): the opening and
 * end-of-day balance, money in and out, the imported deals' milestones planned that day (Approve, Done on another
 * date, Move), every row with its deal tag and all its actions through the existing DayDetail, and the rows of
 * the day already marked done (greyed out and struck through, with Undo), and
 * every row with its deal tag and all its actions (Done, Postpone, Move, amount, edit, delete) through the
 * existing DayDetail. ‹ › and the arrow keys step to the previous / next day.
 *
 * Esc is the theater's: it closes this modal first.
 */
import { computed, nextTick, onMounted, ref, useId } from 'vue'

import type { DayBucket, DealMilestone, DealMilestoneState, ImportedLiquidityDeal, LiquidityTransaction } from '../../../types/liquidity'
import { formatMoney, formatSignedMoney } from '../../../utils/money'
import { useInjectedDealAttributionLookup } from '../../../composables/useLiquidityDealAttribution'
import { dealKeyOf, NEUTRAL_DEAL_COLOR_HEX, shortDealAddress } from '../dealColors'
import { DEAL_MILESTONE_LABELS } from '../dealMilestoneLabels'
import DayDetail from '../DayDetail.vue'
import DealAttributionTag from '../DealAttributionTag.vue'

const props = defineProps<{
  bucket: DayBucket
  /** The balance at the start of the day: the previous day's end-of-day balance. */
  openingBalanceDollars: number
  milestonesOnThisDay: { deal: ImportedLiquidityDeal; state: DealMilestoneState }[]
  canStepToPreviousDay: boolean
  canStepToNextDay: boolean
  /** The one-off rows of this day already marked done: shown struck through, with Undo. */
  doneTransactionsOfThisDay?: LiquidityTransaction[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'stepDay', direction: -1 | 1): void
  (e: 'approveMilestone', deal: ImportedLiquidityDeal, milestone: DealMilestone): void
  (e: 'approveMilestoneOnAnotherDate', deal: ImportedLiquidityDeal, milestone: DealMilestone): void
  (e: 'moveMilestone', deal: ImportedLiquidityDeal, milestone: DealMilestone): void
  (e: 'editTxn', id: string): void
  (e: 'deleteTxn', id: string): void
  (e: 'addOnDate', date: string): void
  (e: 'markDone', id: string): void
  (e: 'moveToDate', id: string, newEffectiveDate: string): void
  (e: 'changeAmount', id: string, newAmountDollars: number): void
  (e: 'markNotDone', id: string): void
}>()

const MONTH_ABBREVIATIONS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDoneDate(doneAt: string): string {
  const [, month, day] = doneAt.slice(0, 10).split('-')
  return `${MONTH_ABBREVIATIONS[Number(month) - 1] ?? ''} ${Number(day)}`
}

const headingId = useId()
const dealAttributionLookup = useInjectedDealAttributionLookup()

const moneyInDollars = computed(() => props.bucket.transactions.reduce((total, txn) => total + Math.max(txn.amount_dollars, 0), 0))
const moneyOutDollars = computed(() => props.bucket.transactions.reduce((total, txn) => total + Math.min(txn.amount_dollars, 0), 0))

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const longDate = computed(() => {
  const [year, month, day] = props.bucket.date.split('-').map(Number)
  const weekdayIndex = new Date(year!, month! - 1, day!).getDay()
  return `${WEEKDAYS[weekdayIndex]}, ${MONTHS[month! - 1]} ${day}, ${year}`
})

function dealColorHex(deal: ImportedLiquidityDeal): string {
  return dealAttributionLookup?.value.attributionForDealKey(dealKeyOf(deal.deal_board, deal.deal_id))?.dealColorHex ?? NEUTRAL_DEAL_COLOR_HEX
}

/** ← / → step days, unless the focus is in a field that needs the arrows. */
function onKeyDown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && (target.closest('input, textarea, select, [contenteditable="true"]'))) return
  if (event.key === 'ArrowLeft' && props.canStepToPreviousDay) {
    event.preventDefault()
    emit('stepDay', -1)
  } else if (event.key === 'ArrowRight' && props.canStepToNextDay) {
    event.preventDefault()
    emit('stepDay', 1)
  }
}

const panelRef = ref<HTMLElement | null>(null)
onMounted(() => nextTick(() => panelRef.value?.focus()))
</script>

<template>
  <div
    data-testid="theater.day-modal"
    class="day-modal-scrim absolute inset-0 z-40 flex items-stretch justify-center bg-page/70 p-2 backdrop-blur-sm sm:p-6"
    @click.self="emit('close')"
  >
    <div
      ref="panelRef"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="headingId"
      tabindex="-1"
      class="day-modal-panel flex w-full max-w-5xl flex-col overflow-hidden rounded-panel border-ui border-line bg-surface shadow-4 focus:outline-none"
      @keydown="onKeyDown"
    >
      <header class="flex items-center gap-2 border-b border-line px-4 py-3 sm:px-6">
        <UiIconButton data-testid="theater.day-modal.previous" label="Previous day" size="md" :disabled="!canStepToPreviousDay" @click="emit('stepDay', -1)">
          <i class="pi pi-chevron-left text-xs" aria-hidden="true"></i>
        </UiIconButton>
        <h2 :id="headingId" class="min-w-0 flex-1 truncate text-center font-display text-lg font-semibold tracking-display text-fg sm:text-xl">{{ longDate }}</h2>
        <UiIconButton data-testid="theater.day-modal.next" label="Next day" size="md" :disabled="!canStepToNextDay" @click="emit('stepDay', 1)">
          <i class="pi pi-chevron-right text-xs" aria-hidden="true"></i>
        </UiIconButton>
        <UiIconButton data-testid="theater.day-modal.close" label="Close the day" size="md" @click="emit('close')">
          <i class="pi pi-times text-xs" aria-hidden="true"></i>
        </UiIconButton>
      </header>

      <div class="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain p-4 sm:p-6">
        <!-- The day in four figures -->
        <dl data-testid="theater.day-modal.summary" class="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <div class="rounded-card bg-surface-2 px-3 py-2">
            <dt class="text-[10px] uppercase tracking-wider text-fg-muted">Opening</dt>
            <dd class="numeric text-base font-semibold text-fg">{{ formatMoney(openingBalanceDollars) }}</dd>
          </div>
          <div class="rounded-card bg-surface-2 px-3 py-2">
            <dt class="text-[10px] uppercase tracking-wider text-fg-muted">Money in</dt>
            <dd data-testid="theater.day-modal.money-in" class="numeric text-base font-semibold text-positive">{{ formatSignedMoney(moneyInDollars) }}</dd>
          </div>
          <div class="rounded-card bg-surface-2 px-3 py-2">
            <dt class="text-[10px] uppercase tracking-wider text-fg-muted">Money out</dt>
            <dd data-testid="theater.day-modal.money-out" class="numeric text-base font-semibold text-negative">{{ formatSignedMoney(moneyOutDollars) }}</dd>
          </div>
          <div class="rounded-card bg-surface-2 px-3 py-2">
            <dt class="text-[10px] uppercase tracking-wider text-fg-muted">End of day</dt>
            <dd data-testid="theater.day-modal.eod" class="numeric text-base font-bold" :class="bucket.balance_dollars < 0 ? 'text-negative' : 'text-primary'">{{ formatMoney(bucket.balance_dollars) }}</dd>
          </div>
        </dl>

        <!-- The imported deals' milestones planned on this day -->
        <section v-if="milestonesOnThisDay.length" data-testid="theater.day-modal.milestones" aria-label="Milestones on this day">
          <h3 class="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-fg-muted">Milestones on this day</h3>
          <ul class="space-y-1.5">
            <li
              v-for="entry in milestonesOnThisDay"
              :key="`${entry.deal.deal_board}-${entry.deal.deal_id}-${entry.state.milestone}`"
              data-testid="theater.day-modal.milestone"
              class="flex flex-wrap items-center gap-2 rounded-ctl bg-surface-2 px-3 py-2"
              :class="entry.state.approved_at ? 'opacity-60' : ''"
              :style="{ boxShadow: `inset 3px 0 0 ${dealColorHex(entry.deal)}` }"
            >
              <i :class="entry.state.approved_at ? 'pi pi-check-circle text-positive' : 'pi pi-flag text-primary'" class="text-xs" aria-hidden="true"></i>
              <span class="text-sm text-fg">{{ DEAL_MILESTONE_LABELS[entry.state.milestone] }}</span>
              <span class="inline-flex items-center gap-1 rounded-full border-ui border-line px-1.5 text-[10px] text-fg-muted">
                <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: dealColorHex(entry.deal) }" aria-hidden="true"></span>
                {{ shortDealAddress(entry.deal.deal_address) }}
              </span>
              <span class="flex-1"></span>
              <span v-if="entry.state.approved_at" class="text-xs text-positive">approved</span>
              <UiButton
                v-else
                data-testid="theater.day-modal.milestone.approve"
                size="sm"
                variant="secondary"
                class="min-h-8 touch:min-h-11 gap-1 text-positive"
                @click="emit('approveMilestone', entry.deal, entry.state.milestone)"
              ><i class="pi pi-check text-[10px]" aria-hidden="true"></i> Approve</UiButton>
              <UiIconButton
                v-if="!entry.state.approved_at"
                data-testid="theater.day-modal.milestone.done-on-date"
                :label="`Done on another date: ${DEAL_MILESTONE_LABELS[entry.state.milestone]}`"
                title="Done on another date…"
                class="text-positive"
                @click="emit('approveMilestoneOnAnotherDate', entry.deal, entry.state.milestone)"
              >
                <i class="pi pi-calendar-plus text-xs" aria-hidden="true"></i>
              </UiIconButton>
              <UiButton
                data-testid="theater.day-modal.milestone.move"
                size="sm"
                variant="ghost"
                class="min-h-8 touch:min-h-11"
                @click="emit('moveMilestone', entry.deal, entry.state.milestone)"
              >Move</UiButton>
            </li>
          </ul>
        </section>

        <!-- Every row of the day, with its deal and every action -->
        <DayDetail
          :bucket="bucket"
          hide-day-heading
          class="!border-0 !bg-transparent !p-0 !shadow-none"
          @edit-txn="(id) => emit('editTxn', id)"
          @delete-txn="(id) => emit('deleteTxn', id)"
          @add-on-date="(date) => emit('addOnDate', date)"
          @mark-done="(id) => emit('markDone', id)"
          @move-to-date="(id, date) => emit('moveToDate', id, date)"
          @change-amount="(id, dollars) => emit('changeAmount', id, dollars)"
        />

        <!-- The rows of this day already marked done: greyed out, struck through, with Undo -->
        <section v-if="doneTransactionsOfThisDay?.length" data-testid="theater.day-modal.done-rows" aria-label="Done on this day">
          <h3 class="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-fg-muted">Done on this day ({{ doneTransactionsOfThisDay.length }})</h3>
          <ul class="space-y-1">
            <li
              v-for="transaction in doneTransactionsOfThisDay"
              :key="transaction.id"
              :data-testid="`theater.day-modal.done-row.${transaction.id}`"
              class="flex flex-wrap items-center gap-2 rounded-ctl bg-surface-2/60 px-3 py-2 opacity-60"
            >
              <i class="pi pi-check-circle text-xs text-positive" aria-hidden="true"></i>
              <span class="min-w-0 flex-1 truncate text-xs text-fg-muted line-through">{{ transaction.description }}</span>
              <DealAttributionTag :txn="transaction" class="shrink-0" />
              <span class="text-[10px] text-fg-muted">done {{ shortDoneDate(transaction.done_at!) }}</span>
              <span class="numeric shrink-0 text-xs text-fg-muted line-through">{{ formatSignedMoney(transaction.amount_dollars) }}</span>
              <UiButton
                :data-testid="`theater.day-modal.done-row.${transaction.id}.undo`"
                size="sm"
                variant="ghost"
                class="min-h-7 touch:min-h-11 text-primary"
                :aria-label="`Undo done: ${transaction.description}`"
                @click="emit('markNotDone', transaction.id)"
              ><i class="pi pi-undo text-[10px]" aria-hidden="true"></i> Undo</UiButton>
            </li>
          </ul>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.day-modal-scrim {
  animation: day-modal-fade var(--dur-base) var(--ease-standard);
}
.day-modal-panel {
  animation: day-modal-rise var(--dur-slow) var(--ease-emphasized);
}
@keyframes day-modal-fade {
  from { opacity: 0; }
}
@keyframes day-modal-rise {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
}
</style>
