<script setup lang="ts">
/**
 * "Import to liquidity" on a BRRRR deal's modal: opens the preview (nothing is imported before "Import").
 * An imported deal shows "Re-sync liquidity" (or "Liquidity out of date · Review" after an edit changed its rows);
 * a My Deals deal whose Bought copy is imported cannot be imported again and says so.
 */
import { computed, onMounted, ref } from 'vue'

import { useDealLiquidityRows } from '../../composables/useDealLiquidityRows'
import type { LiquidityDealBoard } from '../../types/liquidity'
import UiButton from '../ui/UiButton.vue'
import DealImportPreviewModal from './DealImportPreviewModal.vue'

const props = defineProps<{
  dealBoard: LiquidityDealBoard
  dealId: string
  dealAddress: string
  /** Saves pending edits first, so the preview uses the deal as shown; false = the deal cannot be imported now. */
  savePendingChanges: () => Promise<boolean>
}>()

const { importedDeal, boughtCopyInLiquidity, refreshImportedDeals } = useDealLiquidityRows()
onMounted(refreshImportedDeals)

const thisImportedDeal = computed(() => importedDeal(props.dealBoard, props.dealId))
const importedThroughBoughtCopy = computed(() => props.dealBoard === 'my_deals' ? boughtCopyInLiquidity(props.dealId) : null)
const previewOpen = ref(false)

async function openPreview() {
  if (await props.savePendingChanges()) previewOpen.value = true
}
</script>

<template>
  <span v-if="importedThroughBoughtCopy" data-testid="import-to-liquidity.through-bought-copy" class="text-xs text-fg-muted">
    In liquidity through its <RouterLink to="/bought-deals" class="underline">Bought copy</RouterLink>
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
  <DealImportPreviewModal
    v-if="previewOpen"
    :deal-board="dealBoard"
    :deal-id="dealId"
    :deal-address="dealAddress"
    @close="previewOpen = false"
    @imported="refreshImportedDeals"
  />
</template>
