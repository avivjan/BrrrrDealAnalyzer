<script setup lang="ts">
import { computed } from 'vue';
import type { ActiveDealRes } from '../types';

const props = defineProps<{
  deal: ActiveDealRes;
}>();

const stageColors = {
  1: 'border-l-4 border-l-blue-400 bg-gradient-to-br from-slate-800 to-slate-900', // New
  2: 'border-l-4 border-l-yellow-400 bg-gradient-to-br from-slate-800 to-amber-900/20', // Working
  3: 'border-l-4 border-l-emerald-500 bg-gradient-to-br from-slate-800 to-emerald-900/20', // Brought
  4: 'border-l-4 border-l-purple-400 bg-gradient-to-br from-slate-800 to-slate-900 opacity-80', // Keep
  5: 'border-l-4 border-l-gray-500 bg-slate-900 grayscale opacity-60', // Dead
};

const cardClass = computed(() => {
  return stageColors[props.deal.stage as keyof typeof stageColors] || stageColors[1];
});

const formatMoney = (val?: number) => val ? `$${Math.round(val).toLocaleString()}` : '-';
</script>

<template>
  <div 
    class="p-4 rounded-xl shadow-lg cursor-grab active:cursor-grabbing hover:scale-[1.02] transition-all duration-200 group relative overflow-hidden"
    :class="cardClass"
  >
    <!-- Header: Address -->
    <div class="text-center mb-3">
      <h3 class="font-bold text-white text-sm md:text-base leading-tight">{{ deal.address || 'No Address' }}</h3>
    </div>

    <!-- Task Box -->
    <div v-if="deal.task" class="bg-black/30 rounded-lg p-2 mb-3 text-center border border-white/5">
      <span class="text-xs text-ocean-200 uppercase tracking-wider font-semibold">Current Task</span>
      <p class="text-sm text-white font-medium mt-1 line-clamp-2">{{ deal.task }}</p>
    </div>

    <!-- Key Metrics Grid -->
    <div class="grid grid-cols-2 gap-y-2 gap-x-1 text-xs text-gray-300">
      <div class="flex flex-col">
        <span class="text-[10px] text-gray-500 uppercase">Purchase</span>
        <span class="font-mono text-white">{{ formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : 0) }}</span>
      </div>
      <div class="flex flex-col text-right">
        <span class="text-[10px] text-gray-500 uppercase">Cash Flow</span>
        <span class="font-mono" :class="deal.cash_flow > 0 ? 'text-emerald-400' : 'text-red-400'">
          {{ formatMoney(deal.cash_flow) }}
        </span>
      </div>
      
      <div class="flex flex-col">
        <span class="text-[10px] text-gray-500 uppercase">CoC</span>
        <span class="font-mono text-blue-300">{{ deal.cash_on_cash ? deal.cash_on_cash.toFixed(1) + '%' : '-' }}</span>
      </div>
      <div class="flex flex-col text-right">
        <span class="text-[10px] text-gray-500 uppercase">Cash Needed</span>
        <span class="font-mono text-orange-300">{{ formatMoney(deal.total_cash_needed_for_deal) }}</span>
      </div>
    </div>

    <!-- Footer Stats -->
    <div class="mt-3 pt-2 border-t border-white/5 flex justify-between text-[10px] text-gray-500">
      <span>{{ deal.sqft || '-' }} sqft</span>
      <span>{{ deal.bedrooms || '-' }}bd / {{ deal.bathrooms || '-' }}ba</span>
    </div>
  </div>
</template>
