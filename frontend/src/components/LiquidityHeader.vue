<script setup lang="ts">
import { useLiquidityStore } from "../stores/liquidityStore";
import { onMounted, watch, ref } from "vue";
import { useDebounceFn } from "@vueuse/core";

const liquidityStore = useLiquidityStore();

const miniWhaleInput = ref<number | null>(null);
const bigWhaleInput = ref<number | null>(null);

// Initialize inputs when store data loads (Convert to thousands for display)
watch(
  () => liquidityStore.miniWhale,
  (newVal) => {
    if (
      document.activeElement !== document.getElementById("mini-whale-input")
    ) {
      miniWhaleInput.value = newVal ? newVal / 1000 : 0;
    }
  },
  { immediate: true }
);

watch(
  () => liquidityStore.bigWhale,
  (newVal) => {
    if (document.activeElement !== document.getElementById("big-whale-input")) {
      bigWhaleInput.value = newVal ? newVal / 1000 : 0;
    }
  },
  { immediate: true }
);

onMounted(() => {
  liquidityStore.fetchLiquidity();
});

const debouncedUpdate = useDebounceFn(() => {
  liquidityStore.updateLiquidity(
    (bigWhaleInput.value || 0) * 1000,
    (miniWhaleInput.value || 0) * 1000
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
    notation: "compact", // Make the total also compact if space is tight? Or keep full? User said "add K", usually applies to input.
    // Let's keep total readable. Compact notation (e.g. $1.5M) is good for small widgets.
  }).format(value);
};
</script>

<template>
  <div class="fixed bottom-6 right-6 z-50 pointer-events-none">
    <div
      class="pointer-events-auto bg-white/95 backdrop-blur-md shadow-lg border border-gray-200/60 rounded-2xl p-3 flex flex-col items-center gap-2 transition-all hover:shadow-xl hover:scale-105 origin-bottom-right"
    >
      <!-- Total Liquidity (Center/Top) -->
      <div class="text-center pb-2 border-b border-gray-100 w-full">
        <div
          class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5"
        >
          Global Liquidity
        </div>
        <div
          class="text-xl font-black bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent select-none"
        >
          {{ formatCurrency(liquidityStore.totalLiquidity) }}
        </div>
      </div>

      <div class="flex items-center gap-4 pt-1">
        <!-- Mini Whale (Left) -->
        <div class="flex flex-col items-center group">
          <label
            class="text-[8px] font-bold text-gray-400 uppercase tracking-widest mb-0.5 group-hover:text-blue-400 transition-colors"
            >Mini</label
          >
          <div class="relative flex items-center justify-center">
            <span class="text-gray-400 text-[10px] mr-0.5 select-none">$</span>
            <input
              id="mini-whale-input"
              v-model="miniWhaleInput"
              type="number"
              min="0"
              @input="handleInput"
              class="w-10 bg-transparent text-center text-xs font-semibold text-gray-600 focus:outline-none border-b border-transparent focus:border-blue-400 transition-colors placeholder-gray-300 p-0"
              placeholder="0"
            />
            <span class="text-gray-400 text-[10px] ml-0.5 select-none">k</span>
          </div>
        </div>

        <!-- Divider -->
        <div class="w-px h-6 bg-gray-100"></div>

        <!-- Big Whale (Right) -->
        <div class="flex flex-col items-center group">
          <label
            class="text-[8px] font-bold text-gray-400 uppercase tracking-widest mb-0.5 group-hover:text-indigo-400 transition-colors"
            >Big</label
          >
          <div class="relative flex items-center justify-center">
            <span class="text-gray-400 text-[10px] mr-0.5 select-none">$</span>
            <input
              id="big-whale-input"
              v-model="bigWhaleInput"
              type="number"
              min="0"
              @input="handleInput"
              class="w-10 bg-transparent text-center text-xs font-semibold text-gray-600 focus:outline-none border-b border-transparent focus:border-indigo-400 transition-colors placeholder-gray-300 p-0"
              placeholder="0"
            />
            <span class="text-gray-400 text-[10px] ml-0.5 select-none">k</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Remove spinner from number inputs */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
input[type="number"] {
  -moz-appearance: textfield;
}
</style>
