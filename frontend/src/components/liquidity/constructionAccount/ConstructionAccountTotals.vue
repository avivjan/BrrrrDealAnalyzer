<script setup lang="ts">
/** Totals across every live construction account (tasks/todo/ConstructionAccountPerRehab.md). */
import type { ConstructionAccountTotals } from '../../../types/constructionAccount'
import { formatMoney } from '../../../utils/money'

defineProps<{ totals: ConstructionAccountTotals }>()
</script>

<template>
  <div data-testid="ca.totals" class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
    <UiKpiCard data-testid="ca.totals.balance" label="In the accounts" :value="formatMoney(totals.current_balance_dollars)" icon="pi pi-building-columns" />
    <UiKpiCard data-testid="ca.totals.projected-return" label="Coming back at rehab end" :value="formatMoney(totals.projected_return_at_rehab_end_dollars)"
               :tone="totals.projected_return_at_rehab_end_dollars < 0 ? 'negative' : 'positive'" />
    <UiKpiCard data-testid="ca.totals.safe-to-steal" label="Safe to steal now" :value="formatMoney(totals.safe_to_steal_now_dollars)" />
    <UiKpiCard data-testid="ca.totals.remaining-deposits" label="Deposits still to make" :value="formatMoney(totals.remaining_deposit_dollars)"
               :tone="totals.remaining_deposit_dollars > 0 ? 'warning' : 'neutral'" />
    <UiKpiCard data-testid="ca.totals.top-ups" label="Top-ups needed" :value="formatMoney(totals.top_up_needed_dollars)"
               :tone="totals.top_up_needed_dollars > 0 ? 'negative' : 'neutral'" />
    <UiKpiCard data-testid="ca.totals.attention" label="Need attention" :value="`${totals.accounts_needing_attention_count} of ${totals.linked_account_count}`"
               :tone="totals.accounts_needing_attention_count ? 'warning' : 'neutral'" />
  </div>
</template>
