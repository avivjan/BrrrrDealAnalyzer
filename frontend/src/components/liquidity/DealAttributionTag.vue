<script setup lang="ts">
/**
 * The deal a liquidity row came from: a dot in the deal's color and its street address. Nothing for a manual
 * row, a recurring occurrence, or when no deal lookup is provided (tasks/todo/LiquidityTheaterMode.md, section B).
 * The address is always shown with the color, so the deal is never told by color alone.
 *
 * With `linksToTheDeal` (a row in the day view, the overdue strip) the tag opens the deal's modal on its board, and
 * a construction account row gets a second link to that account (tasks/todo/ConstructionAccountPerRehab.md, Step C0).
 */
import { computed } from 'vue'

import { useInjectedDealAttributionLookup } from '../../composables/useLiquidityDealAttribution'
import { constructionAccountOfDeal, dealOnItsBoard } from '../../navigation/appLinks'
import type { LiquidityTransaction } from '../../types/liquidity'

const props = withDefaults(defineProps<{ txn: LiquidityTransaction; linksToTheDeal?: boolean }>(), { linksToTheDeal: false })

const dealAttributionLookup = useInjectedDealAttributionLookup()
const dealAttribution = computed(() => dealAttributionLookup?.value.attributionForTransaction(props.txn) ?? null)
const dealLink = computed(() => props.linksToTheDeal && props.txn.source_deal_board && props.txn.source_deal_id
  ? dealOnItsBoard(props.txn.source_deal_board, props.txn.source_deal_id) : null)
const constructionAccountLink = computed(() => props.linksToTheDeal && props.txn.source_deal_board === 'bought' && props.txn.source_deal_id
  && (props.txn.source_item_key ?? '').startsWith('construction_account_') ? constructionAccountOfDeal(props.txn.source_deal_id) : null)
const TAG_CLASS = 'inline-flex min-w-0 max-w-full items-center gap-1 rounded-full border-ui border-line bg-surface px-1.5 py-px text-[10px] font-medium leading-4 text-fg-muted'
</script>

<template>
  <span v-if="dealAttribution" class="inline-flex min-w-0 max-w-full items-center gap-1">
    <component
      :is="dealLink ? 'RouterLink' : 'span'"
      :to="dealLink ?? undefined"
      :data-testid="`deal-tag.${txn.id}`"
      :data-deal-key="dealAttribution.dealKey"
      :class="[TAG_CLASS, dealLink ? 'hover:border-primary hover:text-primary' : '']"
      :title="dealLink ? `Open ${dealAttribution.dealAddress}` : `From ${dealAttribution.dealAddress}`"
    >
      <span class="h-2 w-2 shrink-0 rounded-full" :style="{ backgroundColor: dealAttribution.dealColorHex }" aria-hidden="true"></span>
      <span class="truncate">{{ dealAttribution.shortDealAddress }}</span>
    </component>
    <RouterLink
      v-if="constructionAccountLink"
      :to="constructionAccountLink"
      :data-testid="`deal-tag.${txn.id}.construction-account`"
      :class="[TAG_CLASS, 'hover:border-primary hover:text-primary']"
      title="Open the construction account"
      :aria-label="`Construction account of ${dealAttribution.dealAddress}`"
    >
      <i class="pi pi-building-columns text-[9px]" aria-hidden="true"></i>
    </RouterLink>
  </span>
</template>
