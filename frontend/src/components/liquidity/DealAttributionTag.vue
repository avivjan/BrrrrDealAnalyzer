<script setup lang="ts">
/**
 * The deal a liquidity row came from: a dot in the deal's color and its street address. Nothing for a manual
 * row, a recurring occurrence, or when no deal lookup is provided (tasks/todo/LiquidityTheaterMode.md, section B).
 * The address is always shown with the color, so the deal is never told by color alone.
 */
import { computed } from 'vue'

import { useInjectedDealAttributionLookup } from '../../composables/useLiquidityDealAttribution'
import type { LiquidityTransaction } from '../../types/liquidity'

const props = defineProps<{ txn: LiquidityTransaction }>()

const dealAttributionLookup = useInjectedDealAttributionLookup()
const dealAttribution = computed(() => dealAttributionLookup?.value.attributionForTransaction(props.txn) ?? null)
</script>

<template>
  <span
    v-if="dealAttribution"
    :data-testid="`deal-tag.${txn.id}`"
    :data-deal-key="dealAttribution.dealKey"
    class="inline-flex min-w-0 max-w-full items-center gap-1 rounded-full border-ui border-line bg-surface px-1.5 py-px text-[10px] font-medium leading-4 text-fg-muted"
    :title="`From ${dealAttribution.dealAddress}`"
  >
    <span class="h-2 w-2 shrink-0 rounded-full" :style="{ backgroundColor: dealAttribution.dealColorHex }" aria-hidden="true"></span>
    <span class="truncate">{{ dealAttribution.shortDealAddress }}</span>
  </span>
</template>
