<template>
  <div
    class="mb-3 rounded-xl bg-gradient-to-br p-3 text-left shadow-glow cursor-pointer"
    :class="stageColor"
    :data-id="deal.id"
    @click="emit('select')"
  >
    <p class="text-sm font-semibold text-slate-100 text-center">{{ deal.address || 'Address TBD' }}</p>
    <p class="mt-2 rounded-lg bg-black/10 p-2 text-xs text-slate-200">{{ deal.task || 'No task yet' }}</p>
    <div class="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-100">
      <div><span class="text-slate-300">Sqft:</span> {{ deal.sqft || '—' }}</div>
      <div><span class="text-slate-300">Beds:</span> {{ deal.bedrooms || '—' }} / Bath {{ deal.bathrooms || '—' }}</div>
      <div><span class="text-slate-300">Purchase:</span> {{ currency(deal.purchasePrice) }}</div>
      <div><span class="text-slate-300">Rehab:</span> {{ currency(deal.rehabCost) }}</div>
      <div><span class="text-slate-300">Cash Flow:</span> {{ currency(deal.cash_flow) }}</div>
      <div><span class="text-slate-300">Cash Needed:</span> {{ currency(deal.total_cash_needed_for_deal) }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { stageColors } from '../../types/deal';
import type { Deal } from '../../types/deal';

const props = defineProps<{ deal: Deal }>();
const emit = defineEmits(['select']);

const stageColor = computed(() => stageColors[props.deal.stage || 1]);

const currency = (value?: number) => {
  if (value === undefined || value === null) return '—';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
};
</script>
