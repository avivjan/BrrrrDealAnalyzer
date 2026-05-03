<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import api from '../../api';
import { useRepsStore } from '../../stores/repsStore';
import {
  REPS_ACTIVITY_CATEGORIES,
  type RepsLogPayload,
  type RepsUser,
} from '../../types/reps';

const props = defineProps<{
  open: boolean;
  user: RepsUser;
  // Pre-filled from the timer when "Finish & Log" is clicked.
  initialStartIso?: string | null;
  initialEndIso?: string | null;
  // Min description length pulled from /reps/config-status (defaults to 20).
  minDescriptionLength?: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved'): void;
}>();

const store = useRepsStore();

const MIN_DESC = computed(() => props.minDescriptionLength ?? 20);

// --- Form state --- //
const propertyName = ref('');
const propertyQuery = ref('');
const showPropertyDropdown = ref(false);
const activityCategory = ref<string>('');
const description = ref('');
// HTML datetime-local inputs: yyyy-MM-ddTHH:mm
const startLocal = ref('');
const endLocal = ref('');
const evidenceLink = ref('');
const evidenceFile = ref<File | null>(null);
const evidenceFileName = ref('');
const location = ref('');
const materialParticipation = ref(false);
const peopleSelected = ref<Set<string>>(new Set());
const newPersonName = ref('');

const uploadingEvidence = ref(false);
const evidenceError = ref('');
const submitting = ref(false);
const formError = ref('');

function isoToLocal(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localToIso(local: string): string {
  if (!local) return '';
  return new Date(local).toISOString();
}

function resetForm() {
  propertyName.value = '';
  propertyQuery.value = '';
  showPropertyDropdown.value = false;
  activityCategory.value = '';
  description.value = '';
  startLocal.value = '';
  endLocal.value = '';
  evidenceLink.value = '';
  evidenceFile.value = null;
  evidenceFileName.value = '';
  location.value = '';
  materialParticipation.value = false;
  peopleSelected.value = new Set();
  newPersonName.value = '';
  uploadingEvidence.value = false;
  evidenceError.value = '';
  submitting.value = false;
  formError.value = '';
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return;
    resetForm();
    startLocal.value = isoToLocal(props.initialStartIso) || isoToLocal(new Date().toISOString());
    endLocal.value = isoToLocal(props.initialEndIso) || isoToLocal(new Date().toISOString());
    // Lazy-load reference data on first open.
    if (store.properties.length === 0) {
      try { await store.fetchProperties(); } catch (err) { console.warn(err); }
    }
    if (store.people.length === 0) {
      try { await store.fetchPeople(); } catch (err) { console.warn(err); }
    }
  },
  { immediate: true },
);

const filteredProperties = computed(() => {
  const q = propertyQuery.value.trim().toLowerCase();
  if (!q) return store.properties;
  return store.properties.filter(p => p.name.toLowerCase().includes(q));
});

const isExactMatch = computed(() => {
  const q = propertyQuery.value.trim().toLowerCase();
  if (!q) return true;
  return store.properties.some(p => p.name.toLowerCase() === q);
});

function pickProperty(name: string) {
  propertyName.value = name;
  propertyQuery.value = name;
  showPropertyDropdown.value = false;
}

// Defer hide so a click on a dropdown entry registers before blur fires.
function onPropertyBlur() {
  window.setTimeout(() => {
    showPropertyDropdown.value = false;
  }, 150);
}

const totalHours = computed(() => {
  if (!startLocal.value || !endLocal.value) return 0;
  const start = new Date(startLocal.value).getTime();
  const end = new Date(endLocal.value).getTime();
  if (!isFinite(start) || !isFinite(end) || end <= start) return 0;
  return Math.round(((end - start) / 3_600_000) * 100) / 100;
});

const descRemaining = computed(() => Math.max(0, MIN_DESC.value - description.value.trim().length));
const descTooShort = computed(() => description.value.trim().length < MIN_DESC.value);

const ALLOWED_FILE_EXTS = ['.pdf', '.jpg', '.jpeg', '.png', '.mov', '.mp4'];
const ALLOWED_FILE_ACCEPT = ALLOWED_FILE_EXTS.join(',');

async function onFileSelected(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  evidenceError.value = '';
  const ext = ('.' + file.name.split('.').pop()!).toLowerCase();
  if (!ALLOWED_FILE_EXTS.includes(ext)) {
    evidenceError.value = `Only ${ALLOWED_FILE_EXTS.join(', ')} allowed.`;
    input.value = '';
    return;
  }
  evidenceFile.value = file;
  evidenceFileName.value = file.name;

  // Trigger upload immediately on selection (per spec) so the URL is ready
  // by the time the user clicks "Save".
  uploadingEvidence.value = true;
  try {
    const res = await api.uploadRepsEvidence(props.user, file);
    evidenceLink.value = res.url;
  } catch (err: any) {
    evidenceError.value = err?.response?.data?.detail || 'Upload failed';
    evidenceFile.value = null;
    evidenceFileName.value = '';
  } finally {
    uploadingEvidence.value = false;
  }
}

function clearEvidence() {
  evidenceFile.value = null;
  evidenceFileName.value = '';
  evidenceLink.value = '';
  evidenceError.value = '';
}

function togglePerson(name: string) {
  const s = new Set(peopleSelected.value);
  if (s.has(name)) s.delete(name);
  else s.add(name);
  peopleSelected.value = s;
}

async function quickAddPerson() {
  const name = newPersonName.value.trim();
  if (!name) return;
  try {
    await store.addPerson({ name });
    togglePerson(name);
    newPersonName.value = '';
  } catch (err: any) {
    formError.value = err?.response?.data?.detail || 'Failed to add person';
  }
}

async function save() {
  formError.value = '';

  if (!startLocal.value || !endLocal.value) {
    formError.value = 'Start and end times are required.';
    return;
  }
  if (new Date(endLocal.value).getTime() <= new Date(startLocal.value).getTime()) {
    formError.value = 'End time must be after start time.';
    return;
  }
  if (descTooShort.value) {
    formError.value = `Description must be at least ${MIN_DESC.value} characters (be specific!).`;
    return;
  }

  // If user typed a property name not in the dropdown, persist it as a prospect.
  const finalProperty = (propertyName.value || propertyQuery.value).trim();
  if (finalProperty && !isExactMatch.value) {
    try {
      await store.ensureProspect(finalProperty);
    } catch (err) {
      console.warn('Failed to save prospect:', err);
    }
  }

  const payload: RepsLogPayload = {
    user: props.user,
    property_name: finalProperty || null,
    activity_category: activityCategory.value || null,
    description: description.value.trim(),
    start_time: localToIso(startLocal.value),
    end_time: localToIso(endLocal.value),
    evidence_link: evidenceLink.value || null,
    location: location.value.trim() || null,
    material_participation_rentals: materialParticipation.value,
    people_involved: Array.from(peopleSelected.value),
  };

  submitting.value = true;
  try {
    await api.logRepsEntry(payload);
    // Refresh the user's entries+stats from the sheet so the dashboard updates.
    await store.fetchEntries(props.user);
    emit('saved');
    emit('close');
  } catch (err: any) {
    formError.value = err?.response?.data?.detail || err?.message || 'Failed to save entry';
  } finally {
    submitting.value = false;
  }
}

function close() {
  if (submitting.value) return;
  emit('close');
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
    @click.self="close"
  >
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
      <header class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
        <div>
          <h3 class="text-lg font-bold text-slate-800">
            New REPS Entry · {{ user }}
          </h3>
          <p class="text-xs font-mono text-slate-500">
            Total: <span class="font-bold text-slate-700">{{ totalHours.toFixed(2) }} h</span>
            · server stamps Created-At at save
          </p>
        </div>
        <button
          class="text-slate-400 hover:text-slate-700 transition-colors"
          @click="close"
        >
          <i class="pi pi-times text-lg"></i>
        </button>
      </header>

      <div class="p-6 space-y-4 overflow-y-auto flex-1">
        <div v-if="formError" class="p-3 rounded-lg bg-rose-100 text-rose-700 text-sm font-medium">
          {{ formError }}
        </div>

        <!-- Property autocomplete -->
        <div class="relative">
          <label class="block text-sm font-medium text-slate-700 mb-1">Property Name</label>
          <input
            v-model="propertyQuery"
            type="text"
            placeholder="Type or pick a property... (e.g. 10th St, Honda, Galveston)"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            @focus="showPropertyDropdown = true"
            @input="propertyName = propertyQuery"
            @blur="onPropertyBlur"
          />
          <div
            v-if="showPropertyDropdown && (filteredProperties.length > 0 || (propertyQuery.trim() && !isExactMatch))"
            class="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg"
          >
            <button
              v-for="opt in filteredProperties"
              :key="opt.name"
              type="button"
              class="w-full text-left px-3 py-2 hover:bg-slate-100 flex items-center justify-between"
              @mousedown.prevent="pickProperty(opt.name)"
            >
              <span class="text-sm text-slate-800">{{ opt.name }}</span>
              <span
                class="text-[10px] font-mono uppercase px-2 py-0.5 rounded"
                :class="opt.source === 'bought' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'"
              >
                {{ opt.source }}
              </span>
            </button>
            <div
              v-if="propertyQuery.trim() && !isExactMatch"
              class="px-3 py-2 text-xs text-slate-500 border-t border-slate-100 italic"
            >
              "{{ propertyQuery }}" will be saved to Prospects on submit.
            </div>
          </div>
        </div>

        <!-- Activity category -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Activity Category</label>
          <select
            v-model="activityCategory"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none bg-white"
          >
            <option value="">— Select —</option>
            <option v-for="c in REPS_ACTIVITY_CATEGORIES" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>

        <!-- Description -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">
            Description <span class="text-rose-500">*</span>
            <span class="text-xs font-normal text-slate-500">
              (≥ {{ MIN_DESC }} chars — be specific, e.g. "Met with Gilly at Honda to review plumbing")
            </span>
          </label>
          <textarea
            v-model="description"
            rows="3"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            :class="descTooShort ? 'border-rose-300' : 'border-slate-300'"
          ></textarea>
          <div class="text-[11px] font-mono mt-1" :class="descTooShort ? 'text-rose-500' : 'text-emerald-600'">
            <span v-if="descTooShort">{{ descRemaining }} more characters required</span>
            <span v-else>{{ description.trim().length }} chars</span>
          </div>
        </div>

        <!-- Times -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Start Time <span class="text-rose-500">*</span></label>
            <input
              v-model="startLocal"
              type="datetime-local"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">End Time <span class="text-rose-500">*</span></label>
            <input
              v-model="endLocal"
              type="datetime-local"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <!-- Material participation -->
        <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <label class="flex items-start gap-2 cursor-pointer">
            <input v-model="materialParticipation" type="checkbox" class="mt-1" />
            <div>
              <div class="text-sm font-medium text-slate-700">
                Material Participation in rentals?
              </div>
              <div class="text-[11px] text-slate-500">
                Counts toward the 500-hour material participation test (in addition to the 750-hour test).
              </div>
            </div>
          </label>
        </div>

        <!-- Location -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Location (GPS or Remote)</label>
          <input
            v-model="location"
            type="text"
            placeholder="e.g. Honda — 1234 Maple St, or Remote"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <!-- Evidence upload -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">
            Evidence (PDF / image / video)
          </label>
          <div class="flex items-center gap-2">
            <input
              type="file"
              :accept="ALLOWED_FILE_ACCEPT"
              :disabled="uploadingEvidence"
              class="block w-full text-sm text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 file:font-medium file:cursor-pointer"
              @change="onFileSelected"
            />
            <button
              v-if="evidenceLink || evidenceFileName"
              type="button"
              class="text-xs text-rose-600 hover:underline"
              @click="clearEvidence"
            >
              Clear
            </button>
          </div>
          <div v-if="uploadingEvidence" class="text-[11px] text-blue-600 mt-1">
            <i class="pi pi-spin pi-spinner mr-1"></i> Uploading to Cloud Storage...
          </div>
          <div v-else-if="evidenceLink" class="text-[11px] text-emerald-600 mt-1 break-all">
            <i class="pi pi-check-circle mr-1"></i>
            <a :href="evidenceLink" target="_blank" class="underline">{{ evidenceFileName || 'Uploaded' }}</a>
          </div>
          <div v-if="evidenceError" class="text-[11px] text-rose-600 mt-1">{{ evidenceError }}</div>
        </div>

        <!-- People involved -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">People Involved</label>
          <div v-if="store.people.length === 0" class="text-xs text-slate-500 mb-2">
            No people yet. Add some on the People tab, or quick-add below.
          </div>
          <div v-else class="flex flex-wrap gap-1.5 mb-2">
            <button
              v-for="p in store.people"
              :key="p.id"
              type="button"
              class="px-2.5 py-1 text-xs rounded-full border transition-colors"
              :class="peopleSelected.has(p.name) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'"
              @click="togglePerson(p.name)"
            >
              {{ p.name }}<span v-if="p.role" class="opacity-75 ml-1">· {{ p.role }}</span>
            </button>
          </div>
          <div class="flex gap-2">
            <input
              v-model="newPersonName"
              type="text"
              placeholder="Quick add a person..."
              class="flex-1 px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
              @keyup.enter="quickAddPerson"
            />
            <button
              type="button"
              class="px-3 py-1.5 text-sm bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700"
              @click="quickAddPerson"
            >
              <i class="pi pi-plus"></i>
            </button>
          </div>
        </div>
      </div>

      <footer class="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-between items-center">
        <div class="text-[11px] font-mono text-slate-500">
          Once saved, this row is append-only — corrections must be a new entry.
        </div>
        <div class="flex gap-2">
          <button
            type="button"
            class="px-4 py-2 text-slate-600 hover:bg-slate-200 rounded-lg font-medium transition-colors"
            :disabled="submitting"
            @click="close"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-2"
            :disabled="submitting || uploadingEvidence"
            @click="save"
          >
            <i v-if="submitting" class="pi pi-spin pi-spinner"></i>
            {{ submitting ? 'Saving...' : 'Save Entry' }}
          </button>
        </div>
      </footer>
    </div>
  </div>
</template>
