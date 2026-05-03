<script setup lang="ts">
import { computed, ref } from 'vue';
import type { RepsEntryRow } from '../../types/reps';

const props = defineProps<{
  entries: RepsEntryRow[];
  loading?: boolean;
  error?: string | null;
}>();

const filterMaterial = ref<'all' | 'material' | 'non-material'>('all');
const filterPerson = ref<string>('');
const search = ref('');

const allPeople = computed(() => {
  const set = new Set<string>();
  for (const e of props.entries) {
    for (const p of e.people_involved || []) set.add(p);
  }
  return Array.from(set).sort();
});

const filtered = computed(() => {
  return props.entries
    .slice()
    .sort((a, b) => (b.start_time || '').localeCompare(a.start_time || ''))
    .filter(e => {
      if (filterMaterial.value === 'material' && !e.material_participation_rentals) return false;
      if (filterMaterial.value === 'non-material' && e.material_participation_rentals) return false;
      if (filterPerson.value && !(e.people_involved || []).includes(filterPerson.value)) return false;
      if (search.value) {
        const q = search.value.toLowerCase();
        const hay = [e.description, e.property_name, e.activity_category, e.location].filter(Boolean).join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
});

function fmtDate(iso: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function fmtTimeRange(start: string | null, end: string | null) {
  if (!start || !end) return '—';
  try {
    const s = new Date(start);
    const e = new Date(end);
    const fmt = (d: Date) => d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    return `${fmt(s)} – ${fmt(e)}`;
  } catch {
    return '—';
  }
}
</script>

<template>
  <div class="rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div class="p-4 border-b border-slate-100 flex flex-wrap items-center gap-3 justify-between">
      <h3 class="text-lg font-bold text-slate-800">Logged Entries</h3>
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="search"
          type="text"
          placeholder="Search descriptions..."
          class="px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
        <select
          v-model="filterMaterial"
          class="px-2 py-1.5 text-sm border border-slate-300 rounded-lg bg-white"
        >
          <option value="all">All entries</option>
          <option value="material">Material (500h)</option>
          <option value="non-material">Non-material</option>
        </select>
        <select
          v-if="allPeople.length > 0"
          v-model="filterPerson"
          class="px-2 py-1.5 text-sm border border-slate-300 rounded-lg bg-white"
        >
          <option value="">Filter person...</option>
          <option v-for="p in allPeople" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="p-6 text-center text-sm text-slate-500">
      <i class="pi pi-spin pi-spinner mr-1"></i> Loading entries from sheet...
    </div>
    <div v-else-if="error" class="p-6 text-center text-sm text-rose-600">
      {{ error }}
    </div>
    <div v-else-if="filtered.length === 0" class="p-6 text-center text-sm text-slate-500">
      No entries match your filters.
    </div>
    <ul v-else class="divide-y divide-slate-100 max-h-[480px] overflow-y-auto">
      <li
        v-for="(e, idx) in filtered"
        :key="(e.created_at || '') + idx"
        class="p-4 flex flex-col gap-1 hover:bg-slate-50 transition-colors"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="text-sm text-slate-800 flex-1">
            <span class="font-mono text-[11px] text-slate-500">
              {{ fmtDate(e.start_time) }} · {{ fmtTimeRange(e.start_time, e.end_time) }}
            </span>
            <span class="ml-2 inline-block text-[10px] font-mono uppercase rounded px-1.5 py-0.5"
              :class="e.material_participation_rentals ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'">
              {{ e.material_participation_rentals ? '500h' : '750h' }}
            </span>
            <div class="mt-1 text-sm text-slate-700">
              {{ e.description }}
            </div>
            <div class="mt-1 text-[11px] font-mono text-slate-500 flex flex-wrap gap-x-3 gap-y-0.5">
              <span v-if="e.property_name">
                <i class="pi pi-home text-[10px] mr-1"></i>{{ e.property_name }}
              </span>
              <span v-if="e.activity_category">
                <i class="pi pi-tag text-[10px] mr-1"></i>{{ e.activity_category }}
              </span>
              <span v-if="e.location">
                <i class="pi pi-map-marker text-[10px] mr-1"></i>{{ e.location }}
              </span>
              <span v-if="e.people_involved.length > 0">
                <i class="pi pi-users text-[10px] mr-1"></i>{{ e.people_involved.join(', ') }}
              </span>
              <a
                v-if="e.evidence_link"
                :href="e.evidence_link"
                target="_blank"
                class="text-blue-600 hover:underline"
              >
                <i class="pi pi-paperclip text-[10px] mr-1"></i>Evidence
              </a>
            </div>
          </div>
          <div class="text-right shrink-0">
            <div class="text-lg font-bold tabular-nums text-slate-800">{{ e.total_hours.toFixed(2) }}h</div>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>
