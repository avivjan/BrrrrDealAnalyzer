<script setup lang="ts">
import { computed, ref, watch, onMounted } from "vue";
import { useDealStore } from "../stores/dealStore";

const store = useDealStore();

const animated = ref({
  numDoors: 0,
  totalValue: 0,
  totalDebt: 0,
  equity: 0,
});

const hasDeals = computed(() => store.portfolioStats.numDoors > 0);

function animateTo(
  key: keyof typeof animated.value,
  target: number,
  duration = 800
) {
  const start = animated.value[key];
  const diff = target - start;
  if (diff === 0) return;
  const startTime = performance.now();
  const step = (now: number) => {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    animated.value[key] = start + diff * eased;
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function syncAnimations() {
  const stats = store.portfolioStats;
  animateTo("numDoors", stats.numDoors, 600);
  animateTo("totalValue", stats.totalValue, 900);
  animateTo("totalDebt", stats.totalDebt, 900);
  animateTo("equity", stats.equity, 1000);
}

watch(() => store.portfolioStats, syncAnimations, { deep: true });

onMounted(() => {
  const stats = store.portfolioStats;
  animated.value = { ...stats };
});

function formatMoney(val: number): string {
  const abs = Math.abs(val);
  if (abs >= 1_000_000) {
    return `$${(val / 1_000_000).toFixed(abs >= 10_000_000 ? 1 : 2)}M`;
  }
  if (abs >= 1_000) {
    return `$${(val / 1_000).toFixed(abs >= 100_000 ? 0 : 1)}K`;
  }
  return `$${Math.round(val).toLocaleString()}`;
}
</script>

<template>
  <!--
    The portfolio strip. Script untouched (rAF count-up, `hasDeals`, money
    formatting); the template is v2: four KPI cards on a glass container,
    rendered by the dashboard inside a height-reserved slot so its arrival
    after `fetchDeals` never shifts the layout. Label precedes value in every
    card — the contract test reads "Doors <n>" out of the text.
  -->
  <UiTransition preset="slideUp" appear>
    <UiGlassPanel
      v-if="hasDeals"
      as="section"
      data-testid="statsbar.root"
      aria-label="Portfolio"
      intensity="low"
      padding="sm"
      class="stats-bar"
    >
      <div class="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
        <UiKpiCard label="Doors" icon="pi pi-building" data-testid="statsbar.doors">
          <template #value>{{ Math.round(animated.numDoors) }}</template>
        </UiKpiCard>
        <UiKpiCard label="Total Value" icon="pi pi-chart-line" data-testid="statsbar.value">
          <template #value>{{ formatMoney(animated.totalValue) }}</template>
        </UiKpiCard>
        <UiKpiCard label="Total Debt" icon="pi pi-credit-card" data-testid="statsbar.debt">
          <template #value>{{ formatMoney(animated.totalDebt) }}</template>
        </UiKpiCard>
        <UiKpiCard label="Equity" icon="pi pi-bolt" tone="positive" data-testid="statsbar.equity">
          <template #value>{{ formatMoney(animated.equity) }}</template>
        </UiKpiCard>
      </div>
    </UiGlassPanel>
  </UiTransition>
</template>
