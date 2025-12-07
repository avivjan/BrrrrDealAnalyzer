<script setup lang="ts">
import { useLiquidityStore } from "@/stores/liquidityStore";
import { onMounted, watch, ref } from "vue";
import { useDebounceFn } from "@vueuse/core";

const liquidityStore = useLiquidityStore();

const miniWhaleInput = ref<number | null>(null);
const bigWhaleInput = ref<number | null>(null);

// Initialize inputs when store data loads
watch(
  () => liquidityStore.miniWhale,
  (newVal) => {
    if (document.activeElement !== document.getElementById('mini-whale-input')) {
         miniWhaleInput.value = newVal;
    }
  },
  { immediate: true }
);

watch(
  () => liquidityStore.bigWhale,
  (newVal) => {
    if (document.activeElement !== document.getElementById('big-whale-input')) {
        bigWhaleInput.value = newVal;
    }
  },
  { immediate: true }
);

onMounted(() => {
  liquidityStore.fetchLiquidity();
});

const debouncedUpdate = useDebounceFn(() => {
  liquidityStore.updateLiquidity(
    bigWhaleInput.value || 0,
    miniWhaleInput.value || 0
  );
}, 1000);

const handleInput = () => {
  debouncedUpdate();
};

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
};

// Custom Input Component logic to handle formatting nicely?
// For simplicity and "subtle" feel, maybe just a standard input that shows number, 
// but we display formatted text when not focused? 
// Or just simple number input styled cleanly.

</script>

<template>
  <div class="w-full bg-white/80 backdrop-blur-sm border-b border-gray-200 shadow-sm py-4 px-6 sticky top-0 z-40 transition-all duration-300">
    <div class="max-w-7xl mx-auto flex items-center justify-between">
      
      <!-- Mini Whale (Left) -->
      <div class="flex flex-col items-center group transition-all duration-300 hover:scale-105">
        <label class="text-xs font-semibold uppercase tracking-wider text-gray-400 group-hover:text-blue-500 transition-colors mb-1">
          Mini Whale
        </label>
        <div class="relative">
          <span class="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400 font-light text-lg pointer-events-none">$</span>
          <input
            id="mini-whale-input"
            v-model="miniWhaleInput"
            type="number"
            min="0"
            @input="handleInput"
            class="w-32 bg-transparent text-center text-xl font-medium text-gray-700 focus:outline-none focus:ring-0 border-b border-transparent focus:border-blue-500 placeholder-gray-300 transition-all pl-4"
            placeholder="0"
          />
        </div>
      </div>

      <!-- Total Liquidity (Center) -->
      <div class="flex flex-col items-center justify-center transform hover:scale-110 transition-transform duration-300 cursor-default">
        <span class="text-[10px] font-bold uppercase tracking-[0.2em] text-gray-400 mb-1">Global Liquidity</span>
        <div class="text-4xl font-black bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent drop-shadow-sm">
          {{ formatCurrency(liquidityStore.totalLiquidity) }}
        </div>
      </div>

      <!-- Big Whale (Right) -->
      <div class="flex flex-col items-center group transition-all duration-300 hover:scale-105">
        <label class="text-xs font-semibold uppercase tracking-wider text-gray-400 group-hover:text-indigo-500 transition-colors mb-1">
          Big Whale
        </label>
        <div class="relative">
          <span class="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400 font-light text-lg pointer-events-none">$</span>
          <input
            id="big-whale-input"
            v-model="bigWhaleInput"
            type="number"
            min="0"
            @input="handleInput"
            class="w-32 bg-transparent text-center text-xl font-medium text-gray-700 focus:outline-none focus:ring-0 border-b border-transparent focus:border-indigo-500 placeholder-gray-300 transition-all pl-4"
            placeholder="0"
          />
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* Remove spinner from number inputs */
input[type=number]::-webkit-inner-spin-button, 
input[type=number]::-webkit-outer-spin-button { 
  -webkit-appearance: none; 
  margin: 0; 
}
input[type=number] {
  -moz-appearance: textfield;
}
</style>

