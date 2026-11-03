<script setup lang="ts">
/**
 * The bottom of the full-screen timeline (tasks/todo/LiquidityTheaterMode.md, section D): a collapsed bar that
 * slides a sheet up with one card per deal in the timeline, side by side. Each card lists the deal's five
 * milestones in date order with a Done button (approve it on its planned date; the view decides whether the
 * before -> after list needs a look first) and Move. A done milestone is muted.
 *
 * The sheet moves with `transform` only and sits over the chart, so the chart never resizes.
 */
import { computed, ref } from 'vue'

import { useInjectedDealAttributionLookup } from '../../../composables/useLiquidityDealAttribution'
import type { DealMilestone, DealMilestoneState, ImportedLiquidityDeal } from '../../../types/liquidity'
import { dealKeyOf, NEUTRAL_DEAL_COLOR_HEX, shortDealAddress } from '../dealColors'
import { DEAL_MILESTONE_LABELS } from '../dealMilestoneLabels'

const props = defineProps<{
  importedDeals: ImportedLiquidityDeal[]
  open: boolean
  /** `${dealKey}:${milestone}` of the milestone being approved, for its spinner. */
  milestoneKeyBeingApproved?: string | null
}>()

const emit = defineEmits<{
  (e: 'toggle'): void
  (e: 'highlightDeal', dealKey: string | null): void
  (e: 'approveMilestone', deal: ImportedLiquidityDeal, milestone: DealMilestone): void
  (e: 'moveMilestone', deal: ImportedLiquidityDeal, milestone: DealMilestone): void
}>()

const dealAttributionLookup = useInjectedDealAttributionLookup()

const dealCards = computed(() => props.importedDeals
  .filter(deal => deal.open_row_count > 0)
  .map(deal => {
    const dealKey = dealKeyOf(deal.deal_board, deal.deal_id)
    return {
      deal,
      dealKey,
      dealColorHex: dealAttributionLookup?.value.attributionForDealKey(dealKey)?.dealColorHex ?? NEUTRAL_DEAL_COLOR_HEX,
      shortDealAddress: shortDealAddress(deal.deal_address),
      milestonesInDateOrder: [...deal.milestones].sort((first, second) => first.planned_date.localeCompare(second.planned_date)),
      approvedMilestoneCount: deal.milestones.filter(state => state.approved_at).length,
    }
  }))

const overdueMilestoneCount = computed(() => dealCards.value
  .reduce((total, card) => total + card.deal.milestones.filter(state => state.is_overdue && !state.approved_at).length, 0))

function milestoneKey(dealKey: string, state: DealMilestoneState): string {
  return `${dealKey}:${state.milestone}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function shortDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${MONTHS[Number(month) - 1] ?? ''} ${Number(day)}, ${year}`
}

const carouselRef = ref<HTMLElement | null>(null)
function scrollCarousel(direction: -1 | 1) {
  const carousel = carouselRef.value
  if (!carousel) return
  carousel.scrollBy({ left: direction * Math.max(carousel.clientWidth * 0.8, 280), behavior: 'smooth' })
}
</script>

<template>
  <div class="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex flex-col justify-end">
    <!-- The sheet: slides up from behind the bar. -->
    <section
      id="theater-deals-sheet"
      data-testid="theater.sheet"
      aria-labelledby="theater-sheet-heading"
      :aria-hidden="!open"
      :inert="!open || undefined"
      class="deals-sheet pointer-events-auto border-t border-line bg-surface/95 shadow-4 backdrop-blur-md"
      :class="open ? 'deals-sheet--open' : ''"
    >
      <div class="flex items-center justify-between gap-2 px-4 pt-3">
        <h2 id="theater-sheet-heading" class="text-[11px] font-semibold uppercase tracking-[0.14em] text-fg-muted">Deals &amp; milestones</h2>
        <div v-if="dealCards.length > 1" class="flex gap-1">
          <UiIconButton data-testid="theater.sheet.previous" label="Previous deals" size="sm" @click="scrollCarousel(-1)">
            <i class="pi pi-chevron-left text-[10px]" aria-hidden="true"></i>
          </UiIconButton>
          <UiIconButton data-testid="theater.sheet.next" label="Next deals" size="sm" @click="scrollCarousel(1)">
            <i class="pi pi-chevron-right text-[10px]" aria-hidden="true"></i>
          </UiIconButton>
        </div>
      </div>
      <p v-if="!dealCards.length" class="px-4 pb-4 pt-2 text-sm text-fg-muted">No deal in the timeline yet. Import one from its deal card on My Deals or Bought.</p>
      <div ref="carouselRef" class="flex snap-x snap-mandatory gap-3 overflow-x-auto overscroll-contain px-4 pb-4 pt-2">
        <article
          v-for="card in dealCards"
          :key="card.dealKey"
          data-testid="theater.sheet.deal"
          :data-deal-key="card.dealKey"
          class="w-[19rem] shrink-0 snap-start rounded-card border-ui border-line bg-surface p-3 shadow-1"
          :style="{ boxShadow: `inset 0 3px 0 ${card.dealColorHex}` }"
          @mouseenter="emit('highlightDeal', card.dealKey)"
          @mouseleave="emit('highlightDeal', null)"
        >
          <header class="mb-2 flex items-center gap-2">
            <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: card.dealColorHex }" aria-hidden="true"></span>
            <h3 class="min-w-0 flex-1 truncate text-sm font-semibold text-fg" :title="card.deal.deal_address">{{ card.shortDealAddress }}</h3>
            <span class="shrink-0 text-[10px] text-fg-muted">{{ card.approvedMilestoneCount }}/{{ card.deal.milestones.length }} done</span>
          </header>
          <ol class="space-y-1">
            <li
              v-for="state in card.milestonesInDateOrder"
              :key="state.milestone"
              data-testid="theater.sheet.milestone"
              :data-milestone="state.milestone"
              :data-done="state.approved_at ? 'true' : 'false'"
              class="flex items-center gap-2 rounded-ctl px-1.5 py-1 transition-opacity duration-base ease-standard"
              :class="state.approved_at ? 'opacity-50' : ''"
            >
              <i
                :class="state.approved_at ? 'pi pi-check-circle text-positive' : state.is_overdue ? 'pi pi-exclamation-circle text-negative' : 'pi pi-circle text-fg-muted'"
                class="shrink-0 text-xs"
                aria-hidden="true"
              ></i>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-xs" :class="state.approved_at ? 'text-fg-muted line-through' : 'text-fg'">{{ DEAL_MILESTONE_LABELS[state.milestone] }}</span>
                <span class="block text-[10px] tabular-nums" :class="state.is_overdue && !state.approved_at ? 'text-negative' : 'text-fg-muted'">
                  {{ shortDate(state.planned_date) }}<template v-if="state.is_overdue && !state.approved_at"> · overdue</template>
                </span>
              </span>
              <UiButton
                v-if="!state.approved_at"
                data-testid="theater.sheet.milestone.done"
                size="sm"
                variant="secondary"
                class="min-h-7 touch:min-h-11 gap-1 px-2 text-positive"
                :disabled="milestoneKeyBeingApproved === milestoneKey(card.dealKey, state)"
                :aria-label="`Done: ${DEAL_MILESTONE_LABELS[state.milestone]} of ${card.deal.deal_address}`"
                @click="emit('approveMilestone', card.deal, state.milestone)"
              >
                <i :class="milestoneKeyBeingApproved === milestoneKey(card.dealKey, state) ? 'pi pi-spin pi-spinner' : 'pi pi-check'" class="text-[9px]" aria-hidden="true"></i>
                Done
              </UiButton>
              <UiButton
                data-testid="theater.sheet.milestone.move"
                size="sm"
                variant="ghost"
                class="min-h-7 touch:min-h-11 px-2 text-fg-muted"
                :aria-label="`Move ${DEAL_MILESTONE_LABELS[state.milestone]} of ${card.deal.deal_address}`"
                @click="emit('moveMilestone', card.deal, state.milestone)"
              >Move</UiButton>
            </li>
          </ol>
          <p class="mt-2 text-[10px] text-fg-muted">{{ card.deal.open_row_count }} open rows · {{ card.deal.done_row_count }} done</p>
        </article>
      </div>
    </section>

    <!-- The collapsed bar, always visible. -->
    <button
      type="button"
      data-testid="theater.sheet.toggle"
      class="pointer-events-auto relative z-10 flex h-11 w-full items-center justify-center gap-3 border-t border-line bg-surface/95 px-4 text-sm text-fg backdrop-blur-md hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      :aria-expanded="open"
      aria-controls="theater-deals-sheet"
      @click="emit('toggle')"
    >
      <span class="flex -space-x-1" aria-hidden="true">
        <span v-for="card in dealCards.slice(0, 5)" :key="card.dealKey" class="h-3 w-3 rounded-full ring-2 ring-surface" :style="{ backgroundColor: card.dealColorHex }"></span>
      </span>
      <span class="font-semibold">Deals · {{ dealCards.length }}</span>
      <span v-if="overdueMilestoneCount" data-testid="theater.sheet.overdue-count" class="text-xs text-negative">{{ overdueMilestoneCount }} overdue milestone{{ overdueMilestoneCount === 1 ? '' : 's' }}</span>
      <i class="pi text-xs text-fg-muted transition-transform duration-base ease-standard" :class="open ? 'pi-chevron-down' : 'pi-chevron-up'" aria-hidden="true"></i>
      <kbd class="hidden rounded border-ui border-line px-1 text-[10px] text-fg-muted sm:inline">D</kbd>
    </button>
  </div>
</template>

<style scoped>
.deals-sheet {
  transform: translateY(100%);
  opacity: 0;
  transition:
    transform var(--dur-slow, 320ms) var(--ease-emphasized, cubic-bezier(0.2, 0, 0, 1)),
    opacity var(--dur-base) var(--ease-standard);
}
.deals-sheet--open {
  transform: translateY(0);
  opacity: 1;
}
</style>
