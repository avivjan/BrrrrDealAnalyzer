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
  <UiCard padding="none">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3 p-4">
        <h3 class="text-base font-semibold text-fg">Logged Entries</h3>
        <div class="flex flex-wrap items-center gap-2">
          <input
            data-testid="repsentries.search"
            v-model="search"
            type="text"
            placeholder="Search descriptions..."
            class="ui-input w-full text-sm sm:w-56"
            aria-label="Search entries"
          />
          <select
            data-testid="repsentries.filter-material"
            v-model="filterMaterial"
            class="ui-select w-full text-sm sm:w-auto"
            aria-label="Filter by participation test"
          >
            <option value="all">All entries</option>
            <option value="material">Material (500h)</option>
            <option value="non-material">Non-material</option>
          </select>
          <select
            v-if="allPeople.length > 0"
            data-testid="repsentries.filter-person"
            v-model="filterPerson"
            class="ui-select w-full text-sm sm:w-auto"
            aria-label="Filter by person"
          >
            <option value="">Filter person...</option>
            <option v-for="p in allPeople" :key="p" :data-testid="`repsentries.person-option.${p}`" :value="p">{{ p }}</option>
          </select>
        </div>
      </div>
    </template>

    <div v-if="loading" data-testid="repsentries.loading" class="p-4" aria-busy="true">
      <p class="text-center text-sm text-fg-muted">
        <i class="pi pi-spin pi-spinner mr-1" aria-hidden="true"></i> Loading entries from sheet...
      </p>
      <UiSkeleton :lines="3" class="mt-4" />
    </div>
    <UiEmptyState
      v-else-if="error"
      data-testid="repsentries.error"
      class="m-4 border-negative/40 bg-negative/5"
    >
      {{ error }}
    </UiEmptyState>
    <UiEmptyState v-else-if="filtered.length === 0" data-testid="repsentries.empty" class="m-4">
      No entries match your filters.
    </UiEmptyState>
    <ul
      v-else
      class="custom-scrollbar max-h-[480px] space-y-2 overflow-y-auto overscroll-contain p-3"
    >
      <UiCard
        as="li"
        v-for="(e, idx) in filtered"
        :key="(e.created_at || '') + idx"
        :data-testid="`repsentries.entry.${idx}`"
        tone="surface"
        padding="sm"
        class="hover:bg-surface-muted"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1 text-sm text-fg">
            <span class="text-[11px] tabular text-fg-muted">
              {{ fmtDate(e.start_time) }} · {{ fmtTimeRange(e.start_time, e.end_time) }}
            </span>
            <UiBadge
              class="ml-2 align-middle uppercase"
              :tone="e.material_participation_rentals ? 'positive' : 'neutral'"
            >
              {{ e.material_participation_rentals ? '500h' : '750h' }}
            </UiBadge>
            <div class="mt-1 break-words text-sm text-fg">
              {{ e.description }}
            </div>
            <div class="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-fg-muted">
              <span v-if="e.property_name" class="break-words">
                <i class="pi pi-home mr-1 text-[10px]" aria-hidden="true"></i>{{ e.property_name }}
              </span>
              <span v-if="e.activity_category" class="break-words">
                <i class="pi pi-tag mr-1 text-[10px]" aria-hidden="true"></i>{{ e.activity_category }}
              </span>
              <span v-if="e.location" class="break-words">
                <i class="pi pi-map-marker mr-1 text-[10px]" aria-hidden="true"></i>{{ e.location }}
              </span>
              <span v-if="e.people_involved.length > 0" class="break-words">
                <i class="pi pi-users mr-1 text-[10px]" aria-hidden="true"></i>{{ e.people_involved.join(', ') }}
              </span>
              <!-- Per-file labelled links (preferred) — one chip per file. -->
              <span v-if="(e.evidence_items || []).length > 0" class="flex flex-wrap gap-x-2 gap-y-0.5">
                <a
                  v-for="(it, i) in e.evidence_items"
                  :key="i + (it.url || '')"
                  :data-testid="`repsentries.entry.${idx}.evidence.${i}`"
                  :href="it.url"
                  target="_blank"
                  class="rounded-ctl font-medium text-primary underline-offset-2 hover:underline"
                >
                  <i class="pi pi-paperclip mr-1 text-[10px]" aria-hidden="true"></i>{{ it.label || `Evidence ${i + 1}` }}
                </a>
              </span>
              <!-- Legacy fallback: one bare URL per cell. -->
              <a
                v-else-if="e.evidence_link && /^https?:\/\//.test(e.evidence_link)"
                :data-testid="`repsentries.entry.${idx}.evidence-legacy`"
                :href="e.evidence_link"
                target="_blank"
                class="rounded-ctl font-medium text-primary underline-offset-2 hover:underline"
              >
                <i class="pi pi-paperclip mr-1 text-[10px]" aria-hidden="true"></i>Evidence
              </a>
              <span
                v-else-if="e.evidence_link"
                class="break-words text-fg-muted"
                :title="e.evidence_link"
              >
                <i class="pi pi-paperclip mr-1 text-[10px]" aria-hidden="true"></i>{{ e.evidence_link.split('\n')[0] }}
              </span>
            </div>
          </div>
          <div class="shrink-0 text-right">
            <div class="text-lg font-bold tabular text-fg">{{ e.total_hours.toFixed(2) }}h</div>
          </div>
        </div>
      </UiCard>
    </ul>
  </UiCard>
</template>
