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
  <Transition name="stats-bar">
    <div
      v-if="hasDeals"
      class="stats-bar relative overflow-hidden"
    >
      <div class="stats-bg absolute inset-0"></div>
      <div class="stats-shimmer absolute inset-0"></div>

      <div class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 py-3">
        <div class="flex items-center justify-center gap-3 sm:gap-6 md:gap-10 flex-wrap">
          <!-- Label -->
          <div class="hidden lg:flex items-center gap-2 mr-2">
            <span class="text-amber-300 text-lg">🏆</span>
            <span
              class="text-xs font-bold uppercase tracking-[0.2em] text-white/60"
            >
              Portfolio
            </span>
          </div>

          <!-- Num of Doors -->
          <div class="stat-card">
            <div class="stat-icon-ring stat-icon-doors">
              <i class="pi pi-building text-xs"></i>
            </div>
            <div class="flex flex-col items-start leading-none">
              <span class="stat-label">Doors</span>
              <span class="stat-value text-white">
                {{ Math.round(animated.numDoors) }}
              </span>
            </div>
          </div>

          <div class="stat-divider"></div>

          <!-- Total Value -->
          <div class="stat-card">
            <div class="stat-icon-ring stat-icon-value">
              <i class="pi pi-chart-line text-xs"></i>
            </div>
            <div class="flex flex-col items-start leading-none">
              <span class="stat-label">Total Value</span>
              <span class="stat-value text-emerald-300">
                {{ formatMoney(animated.totalValue) }}
              </span>
            </div>
          </div>

          <div class="stat-divider"></div>

          <!-- Total Debt -->
          <div class="stat-card">
            <div class="stat-icon-ring stat-icon-debt">
              <i class="pi pi-credit-card text-xs"></i>
            </div>
            <div class="flex flex-col items-start leading-none">
              <span class="stat-label">Total Debt</span>
              <span class="stat-value text-blue-300">
                {{ formatMoney(animated.totalDebt) }}
              </span>
            </div>
          </div>

          <div class="stat-divider"></div>

          <!-- Equity -->
          <div class="stat-card equity-card">
            <div class="stat-icon-ring stat-icon-equity">
              <i class="pi pi-bolt text-xs"></i>
            </div>
            <div class="flex flex-col items-start leading-none">
              <span class="stat-label">Equity</span>
              <span class="stat-value equity-value">
                {{ formatMoney(animated.equity) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.stats-bar {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.stats-bg {
  background: linear-gradient(
    135deg,
    #0f172a 0%,
    #1e1b4b 40%,
    #172554 70%,
    #0f172a 100%
  );
}

.stats-shimmer {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.02) 20%,
    rgba(255, 255, 255, 0.05) 50%,
    rgba(255, 255, 255, 0.02) 80%,
    transparent 100%
  );
  animation: shimmer 8s ease-in-out infinite;
}

@keyframes shimmer {
  0%,
  100% {
    transform: translateX(-100%);
  }
  50% {
    transform: translateX(100%);
  }
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0;
}

.equity-card {
  position: relative;
}

.stat-icon-ring {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon-doors {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
}
.stat-icon-value {
  background: rgba(52, 211, 153, 0.15);
  color: #6ee7b7;
}
.stat-icon-debt {
  background: rgba(96, 165, 250, 0.15);
  color: #93c5fd;
}
.stat-icon-equity {
  background: rgba(251, 191, 36, 0.2);
  color: #fcd34d;
}

.stat-label {
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255, 255, 255, 0.4);
  line-height: 1;
  margin-bottom: 2px;
}

.stat-value {
  font-size: 1.05rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.equity-value {
  background: linear-gradient(135deg, #fbbf24, #f59e0b, #d97706);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.stat-divider {
  width: 1px;
  height: 28px;
  background: linear-gradient(
    180deg,
    transparent,
    rgba(255, 255, 255, 0.12),
    transparent
  );
}

/* Entry animation */
.stats-bar-enter-active {
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.stats-bar-leave-active {
  transition: all 0.3s ease-in;
}
.stats-bar-enter-from {
  opacity: 0;
  transform: translateY(-100%);
}
.stats-bar-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}

@media (max-width: 640px) {
  .stat-value {
    font-size: 0.9rem;
  }
  .stat-icon-ring {
    width: 24px;
    height: 24px;
  }
  .stat-divider {
    display: none;
  }
}
</style>
