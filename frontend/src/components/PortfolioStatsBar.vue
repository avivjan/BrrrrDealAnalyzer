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
      data-testid="statsbar.root"
      class="stats-bar relative overflow-hidden"
    >
      <div class="stats-bg absolute inset-0"></div>
      <!--
        `animate-shimmer` is the Tailwind keyframe the config already mirrors
        from this file, so the sweep no longer needs a local `@keyframes`. The
        global reduced-motion rule in `main.css` neutralises it.
      -->
      <div class="stats-shimmer absolute inset-0 animate-shimmer"></div>

      <div class="relative z-10 mx-auto w-full max-w-7xl px-4 py-2 sm:px-6">
        <div class="flex flex-wrap items-center justify-center gap-3 sm:gap-6 md:gap-10">
          <!-- Label -->
          <div class="mr-2 hidden items-center gap-2 lg:flex">
            <span class="text-lg text-chart-3">🏆</span>
            <span
              class="text-xs font-bold uppercase tracking-[0.2em] text-surface/70"
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
              <span class="stat-value tabular text-surface">
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
              <span class="stat-value tabular text-chart-2">
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
              <span class="stat-value tabular text-chart-4">
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
              <span class="stat-value tabular equity-value">
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
/*
 * The bar is a deliberately inverted surface. The token system has no "dark
 * chrome" pair, but `--color-fg` / `--color-surface` is one by construction —
 * they are the ink and the ground of every other surface — so the bar reads
 * ground-as-`fg`, ink-as-`surface` and keeps its contrast in either theme.
 *
 * `--stats-bar-h` is the 60 px the landing page used to subtract by hand. It is
 * a floor, not a fixed height: below 640 px the four figures wrap onto a second
 * row, and a hard height would clip them behind the bar's `overflow: hidden`.
 */
.stats-bar {
  display: flex;
  align-items: center;
  min-height: var(--stats-bar-h);
  border-bottom: 1px solid rgb(var(--color-surface) / 0.08);
}

/*
 * Two layers instead of four colour stops: an opaque `fg` ground with an indigo
 * and a sky wash over it. The washes are the two accent tokens, so the bar
 * follows the palette instead of restating three hand-picked navies.
 */
.stats-bg {
  background:
    linear-gradient(
      135deg,
      rgb(var(--color-primary) / 0) 0%,
      rgb(var(--color-primary) / 0.28) 40%,
      rgb(var(--color-chart-4) / 0.22) 70%,
      rgb(var(--color-primary) / 0) 100%
    ),
    linear-gradient(rgb(var(--color-fg)), rgb(var(--color-fg)));
}

/*
 * The sweep. `rgb(… / 0)` rather than `transparent`, which interpolates through
 * transparent *black* in sRGB and greys the middle of the gradient. The
 * animation itself is the Tailwind `animate-shimmer` utility on the element.
 */
.stats-shimmer {
  background: linear-gradient(
    90deg,
    rgb(var(--color-surface) / 0) 0%,
    rgb(var(--color-surface) / 0.02) 20%,
    rgb(var(--color-surface) / 0.06) 50%,
    rgb(var(--color-surface) / 0.02) 80%,
    rgb(var(--color-surface) / 0) 100%
  );
}

.stat-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
}

.equity-card {
  position: relative;
}

.stat-icon-ring {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon-doors {
  background: rgb(var(--color-surface) / 0.12);
  color: rgb(var(--color-surface) / 0.85);
}
.stat-icon-value {
  background: rgb(var(--color-chart-2) / 0.18);
  color: rgb(var(--color-chart-2));
}
.stat-icon-debt {
  background: rgb(var(--color-chart-4) / 0.18);
  color: rgb(var(--color-chart-4));
}
.stat-icon-equity {
  background: rgb(var(--color-chart-3) / 0.2);
  color: rgb(var(--color-chart-3));
}

/*
 * 12 px is the bottom of the approved type scale; the old 9.6 px label sat
 * below it, and at 40 % white it was under 3:1 on this ground as well.
 */
.stat-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgb(var(--color-surface) / 0.7);
  line-height: 1;
  margin-bottom: 2px;
}

/* Tabular figures come from the `.tabular` utility on the element itself. */
.stat-value {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.25;
}

.equity-value {
  background: linear-gradient(
    135deg,
    rgb(var(--color-chart-3)) 0%,
    rgb(var(--color-chart-3)) 45%,
    rgb(var(--color-warning)) 100%
  );
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.stat-divider {
  width: 1px;
  height: 28px;
  background: linear-gradient(
    180deg,
    rgb(var(--color-surface) / 0) 0%,
    rgb(var(--color-surface) / 0.16) 50%,
    rgb(var(--color-surface) / 0) 100%
  );
}

/*
 * Entry animation. Named properties rather than `all`, so the bar's height and
 * colours are not dragged through the transition alongside the slide.
 */
.stats-bar-enter-active {
  transition:
    opacity var(--dur-slow) var(--ease-emphasized),
    transform var(--dur-slow) var(--ease-emphasized);
}
.stats-bar-leave-active {
  transition:
    opacity var(--dur-base) var(--ease-exit),
    transform var(--dur-base) var(--ease-exit);
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
    font-size: 0.875rem;
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
