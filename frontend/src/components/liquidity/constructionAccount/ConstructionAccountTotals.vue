<script setup lang="ts">
/**
 * Totals across every live construction account (tasks/todo/ConstructionAccountPerRehab.md), as one compact strip so
 * the property cards start right under it, on a phone too (tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md).
 */
import { computed } from 'vue'

import type { ConstructionAccountTotals } from '../../../types/constructionAccount'
import { formatMoney } from '../../../utils/money'

const props = defineProps<{
  totals: ConstructionAccountTotals
  /** The sum of each live card's "Back to you at the end" (the deposits still to come included), so the totals match the cards. */
  moneyBackToYouAtTheEndTotalDollars: number
}>()

const TONE_CLASS = { neutral: 'text-fg', positive: 'text-positive', negative: 'text-negative', warning: 'text-warning' } as const

const totalFigures = computed(() => [
  { testid: 'ca.totals.balance', label: 'In the construction accounts', value: formatMoney(props.totals.current_balance_dollars), tone: 'neutral' as const },
  { testid: 'ca.totals.projected-return', label: 'Back to you when the rehabs end', value: formatMoney(props.moneyBackToYouAtTheEndTotalDollars), tone: 'positive' as const },
  { testid: 'ca.totals.safe-to-steal', label: 'Safe to take out now', value: formatMoney(props.totals.safe_to_steal_now_dollars), tone: 'neutral' as const },
  { testid: 'ca.totals.remaining-deposits', label: 'Deposits you still owe', value: formatMoney(props.totals.remaining_deposit_dollars),
    tone: props.totals.remaining_deposit_dollars > 0 ? 'warning' as const : 'neutral' as const },
  { testid: 'ca.totals.top-ups', label: 'You need to add now', value: formatMoney(props.totals.top_up_needed_dollars),
    tone: props.totals.top_up_needed_dollars > 0 ? 'negative' as const : 'neutral' as const },
  { testid: 'ca.totals.attention', label: 'Rehabs that need you', value: `${props.totals.accounts_needing_attention_count} of ${props.totals.linked_account_count}`,
    tone: props.totals.accounts_needing_attention_count ? 'warning' as const : 'neutral' as const },
])
</script>

<template>
  <UiSurface data-testid="ca.totals" :level="1" padding="sm">
    <dl class="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 xl:grid-cols-6">
      <div v-for="figure in totalFigures" :key="figure.testid" class="min-w-0">
        <dt class="truncate text-xs text-fg-muted">{{ figure.label }}</dt>
        <dd :data-testid="figure.testid" class="numeric text-base font-bold" :class="TONE_CLASS[figure.tone]">{{ figure.value }}</dd>
      </div>
    </dl>
  </UiSurface>
</template>
