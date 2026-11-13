<script setup lang="ts">
/**
 * "Import to liquidity" on a BRRRR deal's modal: opens the preview (nothing is imported before "Import").
 * Next to it, shortcuts to the same deal elsewhere: its rows on the timeline, and (a Bought deal) its construction
 * account. An imported deal shows "Re-sync liquidity" (or "Liquidity out of date · Review" after an edit changed its rows);
 * a My Deals deal whose Bought copy is imported cannot be imported again and says so.
 */
import { computed, onMounted, ref } from 'vue'

import { useDealLiquidityRows } from '../../composables/useDealLiquidityRows'
import type { LiquidityDealBoard } from '../../types/liquidity'
import UiButton from '../ui/UiButton.vue'
import DealImportPreviewModal from './DealImportPreviewModal.vue'
import { constructionAccountOfDeal, dealOnItsBoard, dealOnTheLiquidityTimeline } from '../../navigation/appLinks'

const props = defineProps<{
  dealBoard: LiquidityDealBoard
  dealId: string
  dealAddress: string
  /** Saves pending edits first, so the preview uses the deal as shown; false = the deal cannot be imported now. */
  savePendingChanges: () => Promise<boolean>
}>()

const { importedDeal, boughtCopyInLiquidity, refreshImportedDeals, askToSyncDealRows } = useDealLiquidityRows()
onMounted(refreshImportedDeals)

const thisImportedDeal = computed(() => importedDeal(props.dealBoard, props.dealId))
const importedThroughBoughtCopy = computed(() => props.dealBoard === 'my_deals' ? boughtCopyInLiquidity(props.dealId) : null)
const previewOpen = ref(false)

/** Out of date: the same "This changes the liquidity timeline" prompt as after a save; otherwise the full preview. */
async function openPreview() {
  if (!(await props.savePendingChanges())) return
  if (thisImportedDeal.value?.liquidity_rows_out_of_date) void askToSyncDealRows(props.dealBoard, props.dealId, props.dealAddress)
  else previewOpen.value = true
}
</script>

<template>
  <span v-if="importedThroughBoughtCopy" data-testid="import-to-liquidity.through-bought-copy" class="text-xs text-fg-muted">
    In liquidity through its
    <RouterLink data-testid="import-to-liquidity.open-bought-copy" :to="dealOnItsBoard('bought', importedThroughBoughtCopy.deal_id)" class="underline">Bought copy</RouterLink>
    ·
    <RouterLink data-testid="import-to-liquidity.bought-copy-on-timeline" :to="dealOnTheLiquidityTimeline('bought', importedThroughBoughtCopy.deal_id)" class="underline">on the timeline</RouterLink>
  </span>
  <UiButton
    v-else
    data-testid="import-to-liquidity"
    variant="ghost"
    size="sm"
    class="min-h-9 touch:min-h-11 text-primary hover:bg-primary/10"
    @click="openPreview"
  >
    <i class="pi pi-wallet" aria-hidden="true"></i>
    <template v-if="thisImportedDeal?.liquidity_rows_out_of_date">Liquidity out of date · Review</template>
    <template v-else-if="thisImportedDeal">Re-sync liquidity</template>
    <template v-else>Import to liquidity</template>
  </UiButton>
  <!-- Shortcuts to the same deal elsewhere (tasks/todo/ConstructionAccountPerRehab.md, Step C0) -->
  <RouterLink
    v-if="thisImportedDeal"
    data-testid="import-to-liquidity.on-the-timeline"
    :to="dealOnTheLiquidityTimeline(dealBoard, dealId)"
    class="inline-flex min-h-9 touch:min-h-11 items-center gap-1.5 rounded-ctl px-2 text-sm font-medium text-primary hover:bg-primary/10"
  >
    <i class="pi pi-chart-line" aria-hidden="true"></i>On the timeline
  </RouterLink>
  <RouterLink
    v-if="dealBoard === 'bought'"
    data-testid="import-to-liquidity.construction-account"
    :to="constructionAccountOfDeal(dealId)"
    class="inline-flex min-h-9 touch:min-h-11 items-center gap-1.5 rounded-ctl px-2 text-sm font-medium text-primary hover:bg-primary/10"
  >
    <i class="pi pi-building-columns" aria-hidden="true"></i>Construction account
  </RouterLink>
  <DealImportPreviewModal
    v-if="previewOpen"
    :deal-board="dealBoard"
    :deal-id="dealId"
    :deal-address="dealAddress"
    @close="previewOpen = false"
    @imported="refreshImportedDeals"
  />
</template>
