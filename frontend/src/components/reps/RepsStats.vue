<script setup lang="ts">
import { computed } from 'vue';
import type { RepsStats } from '../../types/reps';

const props = defineProps<{
  stats: RepsStats | null;
  loading?: boolean;
}>();

// Year-progress bar shows the "pace" line. The actual-progress bar shows where
// you are. If actual > year, you are ahead of pace; otherwise pick up the pace.
const yearPct = computed(() => Math.min(100, Math.max(0, props.stats?.year_progress_pct ?? 0)));
const repsPct = computed(() => Math.min(100, Math.max(0, props.stats?.reps_750_pct ?? 0)));
const matPct = computed(() => Math.min(100, Math.max(0, props.stats?.material_500_pct ?? 0)));

const repsAhead = computed(() => (props.stats?.reps_750_pct ?? 0) >= (props.stats?.year_progress_pct ?? 0));
const matAhead = computed(() => (props.stats?.material_500_pct ?? 0) >= (props.stats?.year_progress_pct ?? 0));

function fmt(n: number | undefined | null) {
  if (n == null) return '—';
  return n.toFixed(2);
}
</script>

<template>
  <UiCard data-testid="repsstats.root" padding="lg" class="h-full">
    <UiSectionHeader as="h3" class="mb-6">
      REPS Progress
      <template #actions>
        <div
          v-if="loading"
          data-testid="repsstats.loading"
          class="flex items-center gap-2 text-xs text-fg-muted"
        >
          <i class="pi pi-spin pi-spinner" aria-hidden="true"></i> Loading from sheet...
        </div>
        <div v-else-if="stats" class="text-xs tabular text-fg-muted">
          {{ stats.entry_count }} entries · day {{ stats.days_elapsed }} of {{ stats.days_in_year }}
        </div>
      </template>
    </UiSectionHeader>

    <!-- Top numbers -->
    <div v-reveal.stagger class="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
      <UiStatTile tone="neutral" size="md" data-reveal>
        <template #label>Total Hours</template>
        {{ fmt(stats?.total_hours) }}
      </UiStatTile>
      <UiStatTile tone="neutral" size="md" data-reveal>
        <template #label>Material (Rentals)</template>
        {{ fmt(stats?.material_hours) }}
      </UiStatTile>
      <UiStatTile tone="neutral" size="md" data-reveal>
        <template #label>Avg/Day Total</template>
        {{ fmt(stats?.avg_daily_hours_total) }}
      </UiStatTile>
      <UiStatTile tone="neutral" size="md" data-reveal>
        <template #label>Avg/Day Material</template>
        {{ fmt(stats?.avg_daily_hours_material) }}
      </UiStatTile>
    </div>

    <!-- Year progress bar -->
    <div class="mb-5">
      <div class="mb-1 flex justify-between gap-3 text-xs">
        <span class="text-fg-muted">Year Progress</span>
        <span class="shrink-0 tabular text-fg-muted">{{ yearPct.toFixed(1) }}%</span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-surface-muted">
        <div class="h-full bg-fg-muted/60 transition-all" :style="{ width: yearPct + '%' }"></div>
      </div>
    </div>

    <!-- 750h REPS bar -->
    <div class="mb-5">
      <div class="mb-1 flex justify-between gap-3 text-xs">
        <span class="font-semibold text-fg">
          750h Real Property Trades / Businesses
          <span v-if="stats" class="font-normal tabular text-fg-muted">
            · {{ fmt(stats.total_hours) }} / 750
          </span>
        </span>
        <span class="shrink-0 tabular" :class="repsAhead ? 'text-positive' : 'text-negative'">
          {{ repsPct.toFixed(1) }}% (vs year {{ yearPct.toFixed(1) }}%)
        </span>
      </div>
      <div class="relative h-3 overflow-hidden rounded-full bg-surface-muted">
        <div
          class="absolute left-0 top-0 h-full transition-all"
          :class="repsAhead ? 'bg-positive' : 'bg-negative'"
          :style="{ width: repsPct + '%' }"
        ></div>
        <!-- pace marker -->
        <div
          class="absolute bottom-[-2px] top-[-2px] w-[2px] bg-fg"
          :style="{ left: yearPct + '%' }"
          :title="`Year pace: ${yearPct.toFixed(1)}%`"
        ></div>
      </div>
    </div>

    <!-- 500h Material bar -->
    <div>
      <div class="mb-1 flex justify-between gap-3 text-xs">
        <span class="font-semibold text-fg">
          500h Material Participation in Rentals
          <span v-if="stats" class="font-normal tabular text-fg-muted">
            · {{ fmt(stats.material_hours) }} / 500
          </span>
        </span>
        <span class="shrink-0 tabular" :class="matAhead ? 'text-positive' : 'text-negative'">
          {{ matPct.toFixed(1) }}% (vs year {{ yearPct.toFixed(1) }}%)
        </span>
      </div>
      <div class="relative h-3 overflow-hidden rounded-full bg-surface-muted">
        <div
          class="absolute left-0 top-0 h-full transition-all"
          :class="matAhead ? 'bg-positive' : 'bg-negative'"
          :style="{ width: matPct + '%' }"
        ></div>
        <div
          class="absolute bottom-[-2px] top-[-2px] w-[2px] bg-fg"
          :style="{ left: yearPct + '%' }"
          :title="`Year pace: ${yearPct.toFixed(1)}%`"
        ></div>
      </div>
    </div>
  </UiCard>
</template>
