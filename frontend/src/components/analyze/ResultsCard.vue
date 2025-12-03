<template>
  <div class="card-surface sticky top-24 rounded-2xl p-5">
    <div class="flex items-center justify-between mb-4">
      <p class="text-xs uppercase tracking-[0.25em] text-slate-400">Results</p>
      <slot name="actions" />
    </div>
    <div class="grid grid-cols-2 gap-4 text-sm">
      <div v-for="item in metrics" :key="item.label" class="space-y-1">
        <p class="text-slate-400 text-xs">{{ item.label }}</p>
        <p class="text-lg font-semibold text-ocean-900">{{ formatValue(item.value, item.isCurrency) }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { AnalyzeDealResponse } from '../../types/deal';

const props = defineProps<{ result?: AnalyzeDealResponse | null }>();

const metrics = computed(() => {
  if (!props.result) return [];
  return [
    { label: 'Cash Flow', value: props.result.cash_flow, isCurrency: true },
    { label: 'Cash Out', value: props.result.cash_out, isCurrency: true },
    { label: 'Cash on Cash', value: props.result.cash_on_cash },
    { label: 'ROI', value: props.result.roi },
    { label: 'Equity', value: props.result.equity, isCurrency: true },
    { label: 'DSCR', value: props.result.dscr },
    { label: 'Total Cash Needed', value: props.result.total_cash_needed_for_deal, isCurrency: true },
    { label: 'Net Profit', value: props.result.net_profit, isCurrency: true }
  ];
});

function formatValue(value?: number | null, currency = false) {
  if (value === undefined || value === null) return '—';
  if (value === -1) return '∞';
  if (value === -2) return '-∞';
  if (currency) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
  }
  return Number(value).toFixed(2);
}
</script>
