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
  <div class="rounded-2xl border border-slate-200 bg-white shadow-sm p-6">
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-lg font-bold text-slate-800">REPS Progress</h3>
      <div v-if="loading" class="text-xs font-mono text-slate-500 flex items-center gap-2">
        <i class="pi pi-spin pi-spinner"></i> Loading from sheet...
      </div>
      <div v-else-if="stats" class="text-xs font-mono text-slate-500">
        {{ stats.entry_count }} entries · day {{ stats.days_elapsed }} of {{ stats.days_in_year }}
      </div>
    </div>

    <!-- Top numbers -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="rounded-xl bg-slate-50 border border-slate-100 p-3">
        <div class="text-[11px] uppercase font-mono text-slate-500 tracking-wider">Total Hours</div>
        <div class="text-2xl font-bold text-slate-800 tabular-nums">{{ fmt(stats?.total_hours) }}</div>
      </div>
      <div class="rounded-xl bg-slate-50 border border-slate-100 p-3">
        <div class="text-[11px] uppercase font-mono text-slate-500 tracking-wider">Material (Rentals)</div>
        <div class="text-2xl font-bold text-slate-800 tabular-nums">{{ fmt(stats?.material_hours) }}</div>
      </div>
      <div class="rounded-xl bg-slate-50 border border-slate-100 p-3">
        <div class="text-[11px] uppercase font-mono text-slate-500 tracking-wider">Avg/Day Total</div>
        <div class="text-2xl font-bold text-slate-800 tabular-nums">{{ fmt(stats?.avg_daily_hours_total) }}</div>
      </div>
      <div class="rounded-xl bg-slate-50 border border-slate-100 p-3">
        <div class="text-[11px] uppercase font-mono text-slate-500 tracking-wider">Avg/Day Material</div>
        <div class="text-2xl font-bold text-slate-800 tabular-nums">{{ fmt(stats?.avg_daily_hours_material) }}</div>
      </div>
    </div>

    <!-- Year progress bar -->
    <div class="mb-5">
      <div class="flex justify-between text-xs font-mono mb-1">
        <span class="text-slate-600">Year Progress</span>
        <span class="text-slate-500">{{ yearPct.toFixed(1) }}%</span>
      </div>
      <div class="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div class="h-full bg-slate-400 transition-all" :style="{ width: yearPct + '%' }"></div>
      </div>
    </div>

    <!-- 750h REPS bar -->
    <div class="mb-5">
      <div class="flex justify-between text-xs font-mono mb-1">
        <span class="text-slate-700 font-semibold">
          750h Real Property Trades / Businesses
          <span v-if="stats" class="text-slate-500 font-normal">
            · {{ fmt(stats.total_hours) }} / 750
          </span>
        </span>
        <span :class="repsAhead ? 'text-emerald-600' : 'text-rose-600'">
          {{ repsPct.toFixed(1) }}% (vs year {{ yearPct.toFixed(1) }}%)
        </span>
      </div>
      <div class="relative h-3 bg-slate-100 rounded-full overflow-hidden">
        <div
          class="absolute top-0 left-0 h-full transition-all"
          :class="repsAhead ? 'bg-emerald-500' : 'bg-rose-500'"
          :style="{ width: repsPct + '%' }"
        ></div>
        <!-- pace marker -->
        <div
          class="absolute top-[-2px] bottom-[-2px] w-[2px] bg-slate-700"
          :style="{ left: yearPct + '%' }"
          :title="`Year pace: ${yearPct.toFixed(1)}%`"
        ></div>
      </div>
    </div>

    <!-- 500h Material bar -->
    <div>
      <div class="flex justify-between text-xs font-mono mb-1">
        <span class="text-slate-700 font-semibold">
          500h Material Participation in Rentals
          <span v-if="stats" class="text-slate-500 font-normal">
            · {{ fmt(stats.material_hours) }} / 500
          </span>
        </span>
        <span :class="matAhead ? 'text-emerald-600' : 'text-rose-600'">
          {{ matPct.toFixed(1) }}% (vs year {{ yearPct.toFixed(1) }}%)
        </span>
      </div>
      <div class="relative h-3 bg-slate-100 rounded-full overflow-hidden">
        <div
          class="absolute top-0 left-0 h-full transition-all"
          :class="matAhead ? 'bg-emerald-500' : 'bg-rose-500'"
          :style="{ width: matPct + '%' }"
        ></div>
        <div
          class="absolute top-[-2px] bottom-[-2px] w-[2px] bg-slate-700"
          :style="{ left: yearPct + '%' }"
          :title="`Year pace: ${yearPct.toFixed(1)}%`"
        ></div>
      </div>
    </div>
  </div>
</template>
