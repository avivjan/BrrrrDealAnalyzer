<script setup lang="ts">
/**
 * "Import to liquidity" (and "Review changes" / Re-sync): the full-screen decision view
 * (tasks/todo/DealImpactSimulator.md). This wrapper keeps the props and events its callers use
 * (`ImportDealToLiquidityButton`, the liquidity page).
 */
import type { DealCashRowChanges, LiquidityDealBoard } from '../../types/liquidity'
import DealImpactView from './dealImpact/DealImpactView.vue'

defineProps<{
  dealBoard: LiquidityDealBoard
  dealId: string
  dealAddress: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'imported', result: DealCashRowChanges): void
}>()
</script>

<template>
  <DealImpactView
    :deal-board="dealBoard"
    :deal-id="dealId"
    :deal-address="dealAddress"
    @close="emit('close')"
    @imported="(result) => emit('imported', result)"
  />
</template>
