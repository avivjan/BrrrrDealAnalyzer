<script setup lang="ts">
/**
 * The imported BRRRR deals in the liquidity timeline: each deal's five milestones (planned / approved / overdue)
 * with Approve and Move, its row counts, the "liquidity out of date" badge after a deal edit (Review changes =
 * the re-sync preview), and a filter that lists only that deal's open rows.
 */
import { computed, ref } from 'vue'

import { useInjectedDealAttributionLookup } from '../../composables/useLiquidityDealAttribution'
import type { DealMilestone, ImportedLiquidityDeal, LiquidityTransaction } from '../../types/liquidity'
import { formatSignedMoney } from '../../utils/money'
import UiBadge from '../ui/UiBadge.vue'
import UiButton from '../ui/UiButton.vue'
import { dealKeyOf } from './dealColors'
import { DEAL_MILESTONE_LABELS } from './dealMilestoneLabels'

const props = defineProps<{
  importedDeals: ImportedLiquidityDeal[]
  transactions: LiquidityTransaction[]
}>()

const emit = defineEmits<{
  (e: 'changeMilestone', deal: ImportedLiquidityDeal, milestone: DealMilestone, approve: boolean): void
  (e: 'reviewChanges', deal: ImportedLiquidityDeal): void
  (e: 'removeOpenRows', deal: ImportedLiquidityDeal): void
}>()

/** A deal whose open rows were all removed or done is out of the timeline: only its done rows stay, as history. */
const dealsStillInTheTimeline = computed(() => props.importedDeals.filter(deal => deal.open_row_count > 0))

const dealAttributionLookup = useInjectedDealAttributionLookup()
function dealColorHex(deal: ImportedLiquidityDeal): string | null {
  return dealAttributionLookup?.value.attributionForDealKey(dealKeyOf(deal.deal_board, deal.deal_id))?.dealColorHex ?? null
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}, ${year}`
}

const dealIdShowingRows = ref<string | null>(null)
const openRowsOfTheDealShown = computed(() => props.transactions
  .filter(transaction => transaction.source_deal_id === dealIdShowingRows.value && !transaction.done_at)
  .sort((first, second) => first.effective_date.localeCompare(second.effective_date)
    || (first.sequence_within_day ?? 0) - (second.sequence_within_day ?? 0)))

function toggleRows(deal: ImportedLiquidityDeal) {
  dealIdShowingRows.value = dealIdShowingRows.value === deal.deal_id ? null : deal.deal_id
}

function boardLink(deal: ImportedLiquidityDeal): string {
  return deal.deal_board === 'bought' ? '/bought-deals' : '/my-deals'
}
</script>

<template>
  <section v-if="dealsStillInTheTimeline.length" data-testid="liquidity-deals" aria-label="Imported deals" class="flex flex-col gap-3">
    <h2 class="text-sm font-semibold text-fg">Deals in the timeline</h2>
    <article
      v-for="deal in dealsStillInTheTimeline"
      :key="`${deal.deal_board}-${deal.deal_id}`"
      data-testid="liquidity-deal"
      :data-deal-id="deal.deal_id"
      class="rounded-card border-ui border-line bg-surface p-3 text-sm"
    >
      <header class="flex flex-wrap items-center gap-2">
        <span v-if="dealColorHex(deal)" data-testid="liquidity-deal.color" class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: dealColorHex(deal)! }" aria-hidden="true"></span>
        <RouterLink :to="boardLink(deal)" class="font-semibold text-fg hover:text-primary">{{ deal.deal_address }}</RouterLink>
        <UiBadge tone="neutral">{{ deal.deal_board === 'bought' ? 'Bought' : 'My Deals' }}</UiBadge>
        <UiBadge v-if="deal.overdue_open_row_count" tone="negative">{{ deal.overdue_open_row_count }} overdue</UiBadge>
        <UiBadge v-if="deal.refi_is_late" tone="warning">Refi late · {{ deal.late_refi_row_count }} added rows</UiBadge>
        <UiButton
          v-if="deal.liquidity_rows_out_of_date"
          data-testid="liquidity-deal.review-changes"
          size="sm"
          variant="secondary"
          @click="emit('reviewChanges', deal)"
        >Liquidity out of date · Review changes</UiButton>
      </header>
      <p class="mt-1 text-xs text-fg-muted">{{ deal.open_row_count }} open rows · {{ deal.done_row_count }} done</p>

      <ul class="mt-2 flex flex-col gap-1.5">
        <li
          v-for="state in deal.milestones"
          :key="state.milestone"
          data-testid="liquidity-deal.milestone"
          :data-milestone="state.milestone"
          class="flex flex-wrap items-center justify-between gap-2"
        >
          <span class="flex items-center gap-2">
            <i
              :class="state.approved_at ? 'pi pi-check-circle text-positive' : state.is_overdue ? 'pi pi-exclamation-circle text-negative' : 'pi pi-circle text-fg-muted'"
              class="text-xs"
              aria-hidden="true"
            ></i>
            <span class="text-fg">{{ DEAL_MILESTONE_LABELS[state.milestone] }}</span>
            <span class="tabular-nums text-fg-muted">{{ shortDate(state.planned_date) }}</span>
            <span v-if="state.approved_at" class="text-xs text-positive">approved</span>
            <span v-else-if="state.is_overdue" class="text-xs text-negative">overdue</span>
          </span>
          <span class="flex gap-1">
            <UiButton v-if="!state.approved_at" data-testid="liquidity-deal.milestone.approve" size="sm" variant="secondary"
              @click="emit('changeMilestone', deal, state.milestone, true)">Approve</UiButton>
            <UiButton data-testid="liquidity-deal.milestone.move" size="sm" variant="ghost"
              @click="emit('changeMilestone', deal, state.milestone, false)">Move</UiButton>
          </span>
        </li>
      </ul>

      <div class="mt-2 flex flex-wrap gap-2">
        <button type="button" data-testid="liquidity-deal.toggle-rows" class="text-xs font-semibold text-fg-muted underline" @click="toggleRows(deal)">
          {{ dealIdShowingRows === deal.deal_id ? 'Hide its rows' : 'Show its open rows' }}
        </button>
        <button type="button" data-testid="liquidity-deal.remove-open-rows" class="text-xs font-semibold text-negative underline" @click="emit('removeOpenRows', deal)">
          Deal is dead: remove its open rows
        </button>
      </div>
      <ul v-if="dealIdShowingRows === deal.deal_id" data-testid="liquidity-deal.rows" class="mt-2 flex flex-col gap-0.5 text-xs">
        <li v-for="transaction in openRowsOfTheDealShown" :key="transaction.id" class="flex justify-between gap-3">
          <span class="text-fg-muted">{{ shortDate(transaction.effective_date) }} · {{ transaction.description }}</span>
          <span class="tabular-nums" :class="transaction.amount_dollars < 0 ? 'text-negative' : 'text-positive'">{{ formatSignedMoney(transaction.amount_dollars) }}</span>
        </li>
      </ul>
    </article>
  </section>
</template>
