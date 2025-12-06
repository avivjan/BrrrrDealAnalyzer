<script setup lang="ts">
import { computed } from "vue";
import type { ActiveDealRes } from "../types";

const props = defineProps<{
  deal: ActiveDealRes;
}>();

const emit = defineEmits<{
  (e: "delete", id: number): void;
}>();

const stageColors = {
  1: "border-l-4 border-l-blue-500 bg-white border border-gray-100", // New
  2: "border-l-4 border-l-yellow-500 bg-white border border-gray-100", // Working
  3: "border-l-4 border-l-emerald-500 bg-white border border-gray-100", // Brought
  4: "border-l-4 border-l-purple-500 bg-white border border-gray-100", // Keep
  5: "border-l-4 border-l-gray-400 bg-gray-50 border border-gray-100", // Dead
};

const cardClass = computed(() => {
  return (
    stageColors[props.deal.stage as keyof typeof stageColors] || stageColors[1]
  );
});

const formatMoney = (val?: number) =>
  val ? `$${Math.round(val).toLocaleString()}` : "-";
</script>

<template>
  <div
    class="p-4 rounded-xl shadow-sm hover:shadow-md cursor-grab active:cursor-grabbing hover:scale-[1.02] transition-all duration-200 group relative overflow-hidden"
    :class="cardClass"
  >
    <!-- Delete Button -->
    <button
      @click.stop="emit('delete', deal.id)"
      class="absolute top-2 right-2 p-1.5 rounded-full bg-red-100 text-red-600 opacity-0 group-hover:opacity-100 transition-all hover:bg-red-200 hover:scale-110 z-10"
      title="Delete Deal"
    >
      <i class="pi pi-times text-[10px] font-bold"></i>
    </button>

    <!-- Header: Address -->
    <div class="text-center mb-3">
      <h3 class="font-bold text-gray-900 text-sm md:text-base leading-tight">
        {{ deal.address || "No Address" }}
      </h3>
    </div>

    <!-- Task Box -->
    <div
      v-if="deal.task"
      class="bg-gray-50 rounded-lg p-2 mb-3 text-center border border-gray-200"
    >
      <span class="text-xs text-blue-600 uppercase tracking-wider font-semibold"
        >Current Task</span
      >
      <p class="text-sm text-gray-800 font-medium mt-1 line-clamp-2">
        {{ deal.task }}
      </p>
    </div>

    <!-- Key Metrics Grid -->
    <div class="grid grid-cols-2 gap-y-2 gap-x-1 text-xs text-gray-600">
      <div class="flex flex-col">
        <span class="text-[10px] text-gray-400 uppercase">Purchase</span>
        <span class="font-mono text-gray-900">{{
          formatMoney(deal.purchasePrice ? deal.purchasePrice * 1000 : 0)
        }}</span>
      </div>
      <div class="flex flex-col text-right">
        <span class="text-[10px] text-gray-400 uppercase">Cash Flow</span>
        <span
          class="font-mono"
          :class="deal.cash_flow > 0 ? 'text-emerald-600' : 'text-red-600'"
        >
          {{ formatMoney(deal.cash_flow) }}
        </span>
      </div>

      <div class="flex flex-col">
        <span class="text-[10px] text-gray-400 uppercase">CoC</span>
        <span class="font-mono text-blue-600">{{
          deal.cash_on_cash ? deal.cash_on_cash.toFixed(1) + "%" : "-"
        }}</span>
      </div>
      <div class="flex flex-col text-right">
        <span class="text-[10px] text-gray-400 uppercase">Cash Needed</span>
        <span class="font-mono text-orange-600">{{
          formatMoney(deal.total_cash_needed_for_deal)
        }}</span>
      </div>
    </div>

    <!-- Footer Stats -->
    <div
      class="mt-3 pt-2 border-t border-gray-100 flex justify-between text-[10px] text-gray-400"
    >
      <span>{{ deal.sqft || "-" }} sqft</span>
      <span>{{ deal.bedrooms || "-" }}bd / {{ deal.bathrooms || "-" }}ba</span>
    </div>
  </div>
</template>
