<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import api from '../../api';
import { useRepsStore, captureGeoSnapshot } from '../../stores/repsStore';
import {
  FALLBACK_REPS_ACTIVITY_CATEGORIES,
  type LocationSnapshot,
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
const newCategoryName = ref('');
const addingCategory = ref(false);
const showAddCategory = ref(false);

const description = ref('');
// HTML datetime-local inputs: yyyy-MM-ddTHH:mm
const startLocal = ref('');
const endLocal = ref('');

// Multi-file evidence: any File queued before opening the modal (real-time
// camera shots taken during a session) is merged with files added inside
// the modal here.
const localFiles = ref<File[]>([]);
const evidenceError = ref('');

// Optional manual location override / context (e.g. "Remote", "Property
// site visit"). The actual GPS breadcrumbs come from `pendingSnapshots`
// + a final manual_save snapshot taken when "Save" is clicked.
const locationNote = ref('');
const pendingSnapshots = ref<LocationSnapshot[]>([]);
const capturingSnapshot = ref(false);

const materialParticipation = ref(false);
const peopleSelected = ref<Set<string>>(new Set());
const newPersonName = ref('');

const submitting = ref(false);
const uploadingFiles = ref(false);
const formError = ref('');

const ALLOWED_FILE_EXTS = ['.pdf', '.jpg', '.jpeg', '.png', '.mov', '.mp4'];
const ALLOWED_FILE_ACCEPT = ALLOWED_FILE_EXTS.join(',');

// Files merged from the live timer session + files chosen in the modal.
const allFiles = computed<File[]>(() => [...store.inFlightFilesByUser[props.user], ...localFiles.value]);

const allSnapshots = computed<LocationSnapshot[]>(() => [
  ...store.snapshotsByUser[props.user],
  ...pendingSnapshots.value,
]);

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
  newCategoryName.value = '';
  showAddCategory.value = false;
  description.value = '';
  startLocal.value = '';
  endLocal.value = '';
  localFiles.value = [];
  evidenceError.value = '';
  locationNote.value = '';
  pendingSnapshots.value = [];
  capturingSnapshot.value = false;
  materialParticipation.value = false;
  peopleSelected.value = new Set();
  newPersonName.value = '';
  submitting.value = false;
  uploadingFiles.value = false;
  formError.value = '';
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return;
    resetForm();
    startLocal.value = isoToLocal(props.initialStartIso) || isoToLocal(new Date().toISOString());
    endLocal.value = isoToLocal(props.initialEndIso) || isoToLocal(new Date().toISOString());
    if (store.properties.length === 0) {
      try { await store.fetchProperties(); } catch (err) { console.warn(err); }
    }
    if (store.people.length === 0) {
      try { await store.fetchPeople(); } catch (err) { console.warn(err); }
    }
    if (store.activityCategories.length === 0) {
      try { await store.fetchActivityCategories(); } catch (err) { console.warn(err); }
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

function onPropertyBlur() {
  window.setTimeout(() => { showPropertyDropdown.value = false; }, 150);
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

// Categories shown in the dropdown — server-backed when available, fallback list otherwise.
const categoryOptions = computed<string[]>(() => {
  if (store.activityCategories.length > 0) {
    return store.activityCategories.map(c => c.name);
  }
  return [...FALLBACK_REPS_ACTIVITY_CATEGORIES];
});

// --- File handling --- //

function validateAndAcceptFiles(files: FileList | File[] | null) {
  evidenceError.value = '';
  if (!files) return;
  const accepted: File[] = [];
  for (const f of Array.from(files)) {
    const ext = ('.' + f.name.split('.').pop()!).toLowerCase();
    if (!ALLOWED_FILE_EXTS.includes(ext)) {
      evidenceError.value = `Skipped "${f.name}" — only ${ALLOWED_FILE_EXTS.join(', ')} allowed.`;
      continue;
    }
    accepted.push(f);
  }
  if (accepted.length > 0) {
    localFiles.value = [...localFiles.value, ...accepted];
  }
}

function onFileInputChange(e: Event) {
  const input = e.target as HTMLInputElement;
  validateAndAcceptFiles(input.files);
  input.value = '';
}

function removeFileFromLocal(idx: number) {
  const list = [...localFiles.value];
  list.splice(idx, 1);
  localFiles.value = list;
}

function removeFileFromTimer(idx: number) {
  store.removeInFlightFile(props.user, idx);
}

const cameraInputRef = ref<HTMLInputElement | null>(null);

function openCameraDirect() {
  cameraInputRef.value?.click();
}

// --- People handling --- //

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

// --- Activity-category quick add --- //

async function addCategoryInline() {
  const name = newCategoryName.value.trim();
  if (!name) return;
  addingCategory.value = true;
  try {
    const cat = await store.addActivityCategory(name);
    if (cat) activityCategory.value = cat.name;
    newCategoryName.value = '';
    showAddCategory.value = false;
  } catch (err: any) {
    formError.value = err?.response?.data?.detail || 'Failed to add category';
  } finally {
    addingCategory.value = false;
  }
}

// --- Geolocation --- //

async function captureSnapshotNow(kind: LocationSnapshot['kind'] = 'manual_save') {
  capturingSnapshot.value = true;
  try {
    const snap = await captureGeoSnapshot(kind);
    pendingSnapshots.value = [...pendingSnapshots.value, snap];
  } finally {
    capturingSnapshot.value = false;
  }
}

function markRemote() {
  pendingSnapshots.value = [
    ...pendingSnapshots.value,
    {
      kind: 'manual_save',
      captured_at: new Date().toISOString(),
      note: locationNote.value.trim() || 'Remote',
    },
  ];
}

function dropPendingSnapshot(idx: number) {
  const list = [...pendingSnapshots.value];
  list.splice(idx, 1);
  pendingSnapshots.value = list;
}

function snapshotLabel(s: LocationSnapshot): string {
  const KIND_LABEL: Record<string, string> = {
    manual_save: 'MANUAL',
    timer_start: 'START',
    timer_pause: 'PAUSE',
    timer_resume: 'RESUME',
    timer_stop: 'STOP',
    bookmark: 'BOOKMARK',
    evidence_capture: 'PHOTO',
  };
  return KIND_LABEL[s.kind] || s.kind.toUpperCase();
}

function snapshotMapHref(s: LocationSnapshot): string | null {
  if (s.lat == null || s.lng == null) return null;
  return `https://maps.google.com/?q=${s.lat.toFixed(5)},${s.lng.toFixed(5)}`;
}

// --- Save --- //

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

  const finalProperty = (propertyName.value || propertyQuery.value).trim();
  if (finalProperty && !isExactMatch.value) {
    try { await store.ensureProspect(finalProperty); }
    catch (err) { console.warn('Failed to save prospect:', err); }
  }

  // Note: GPS snapshots are captured ONLY when the user explicitly clicks
  // "Capture GPS now" in the modal or "Pin GPS now" on the timer. Save no
  // longer auto-snaps — the audit trail reflects what the user chose to log.

  // Step 1: upload all queued files into a per-log folder, get back URLs.
  let evidenceFolder: string | null = null;
  let evidenceLinks: string[] = [];
  if (allFiles.value.length > 0) {
    uploadingFiles.value = true;
    try {
      const batch = await api.uploadRepsEvidenceBatch({
        user: props.user,
        files: allFiles.value,
        propertyName: finalProperty || null,
        activityCategory: activityCategory.value || null,
        logTimestamp: new Date().toISOString(),
      });
      evidenceFolder = batch.folder_url || null;
      evidenceLinks = batch.files.map(f => f.url);
    } catch (err: any) {
      uploadingFiles.value = false;
      formError.value = err?.response?.data?.detail || 'Failed to upload evidence';
      return;
    } finally {
      uploadingFiles.value = false;
    }
  }

  const payload: RepsLogPayload = {
    user: props.user,
    property_name: finalProperty || null,
    activity_category: activityCategory.value || null,
    description: description.value.trim(),
    start_time: localToIso(startLocal.value),
    end_time: localToIso(endLocal.value),
    evidence_links: evidenceLinks,
    evidence_folder: evidenceFolder,
    location_snapshots: allSnapshots.value,
    location: locationNote.value.trim() || null,
    material_participation_rentals: materialParticipation.value,
    people_involved: Array.from(peopleSelected.value),
  };

  // Step 2: append the row.
  submitting.value = true;
  try {
    await api.logRepsEntry(payload);
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
  if (submitting.value || uploadingFiles.value) return;
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
        <button class="text-slate-400 hover:text-slate-700 transition-colors" @click="close">
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
          <div class="flex items-center justify-between mb-1">
            <label class="block text-sm font-medium text-slate-700">Activity Category</label>
            <button
              type="button"
              class="text-[11px] font-mono text-blue-600 hover:underline"
              @click="showAddCategory = !showAddCategory"
            >
              <i class="pi pi-plus mr-1"></i>{{ showAddCategory ? 'Cancel' : 'Add new' }}
            </button>
          </div>
          <select
            v-model="activityCategory"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none bg-white"
          >
            <option value="">— Select —</option>
            <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
          </select>
          <div v-if="showAddCategory" class="mt-2 flex gap-2">
            <input
              v-model="newCategoryName"
              type="text"
              placeholder="New category name..."
              class="flex-1 px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
              @keyup.enter="addCategoryInline"
            />
            <button
              type="button"
              class="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50"
              :disabled="addingCategory || !newCategoryName.trim()"
              @click="addCategoryInline"
            >
              <i v-if="addingCategory" class="pi pi-spin pi-spinner"></i>
              <span v-else>Add</span>
            </button>
          </div>
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
            class="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
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

        <!-- Location: GPS breadcrumbs + manual override.
             Capture is ALWAYS manual: nothing is recorded unless the user
             taps "Capture GPS now" or "Mark as Remote". -->
        <div class="rounded-lg border border-slate-200 p-3">
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-medium text-slate-700">
              Location · {{ allSnapshots.length }} GPS pin{{ allSnapshots.length === 1 ? '' : 's' }}
            </label>
            <div class="flex gap-1.5">
              <button
                type="button"
                class="px-2.5 py-1 text-[11px] bg-indigo-100 text-indigo-700 hover:bg-indigo-200 rounded-lg flex items-center gap-1 disabled:opacity-50"
                :disabled="capturingSnapshot"
                @click="captureSnapshotNow('manual_save')"
              >
                <i class="pi pi-map-marker text-[10px]"></i>
                {{ capturingSnapshot ? 'Capturing...' : 'Capture GPS now' }}
              </button>
              <button
                type="button"
                class="px-2.5 py-1 text-[11px] bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-lg"
                @click="markRemote"
              >
                Mark as Remote
              </button>
            </div>
          </div>

          <ul v-if="allSnapshots.length > 0" class="space-y-1 mb-2 max-h-32 overflow-y-auto">
            <li
              v-for="(s, idx) in allSnapshots"
              :key="idx"
              class="text-[11px] font-mono text-slate-700 flex items-start justify-between gap-2 py-0.5"
            >
              <span class="flex-1 truncate">
                <span class="inline-block px-1.5 rounded bg-slate-100 text-slate-700 mr-1">{{ snapshotLabel(s) }}</span>
                <span v-if="s.lat != null && s.lng != null">
                  {{ s.lat.toFixed(5) }}, {{ s.lng.toFixed(5) }}<span v-if="s.accuracy_m"> (±{{ Math.round(s.accuracy_m) }}m)</span>
                </span>
                <span v-else class="text-slate-500">[{{ s.note || 'no GPS' }}]</span>
                <a
                  v-if="snapshotMapHref(s)"
                  :href="snapshotMapHref(s)!"
                  target="_blank"
                  class="text-blue-600 hover:underline ml-1"
                >map</a>
              </span>
              <!-- Only allow dropping breadcrumbs the modal added; timer-driven ones live in the store. -->
              <button
                v-if="idx >= store.snapshotsByUser[user].length"
                type="button"
                class="text-rose-500 hover:text-rose-700 text-xs"
                @click="dropPendingSnapshot(idx - store.snapshotsByUser[user].length)"
              >
                <i class="pi pi-times"></i>
              </button>
            </li>
          </ul>
          <div v-else class="text-[11px] text-slate-500 italic mb-2">
            No location recorded yet. Tap "Capture GPS now" if you want to log
            where you are; otherwise leave the column blank or use the note
            below (e.g. "Remote — phone call").
          </div>

          <input
            v-model="locationNote"
            type="text"
            placeholder="Optional note (e.g. 'Remote — phone call', 'Honda — 1234 Maple St')"
            class="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <!-- Multi-asset evidence -->
        <div class="rounded-lg border border-slate-200 p-3">
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-medium text-slate-700">
              Evidence
              <span
                v-if="allFiles.length > 0"
                class="ml-1 inline-block px-2 py-0.5 text-[10px] font-mono rounded-full bg-blue-100 text-blue-700"
              >
                {{ allFiles.length }} file{{ allFiles.length === 1 ? '' : 's' }} attached
              </span>
            </label>
            <div class="flex gap-1.5">
              <button
                type="button"
                class="px-2.5 py-1 text-[11px] bg-rose-100 text-rose-700 hover:bg-rose-200 rounded-lg flex items-center gap-1"
                @click="openCameraDirect"
              >
                <i class="pi pi-camera text-[10px]"></i> Camera
              </button>
              <label
                class="px-2.5 py-1 text-[11px] bg-blue-100 text-blue-700 hover:bg-blue-200 rounded-lg flex items-center gap-1 cursor-pointer"
              >
                <i class="pi pi-paperclip text-[10px]"></i> Attach
                <input
                  type="file"
                  :accept="ALLOWED_FILE_ACCEPT"
                  multiple
                  class="hidden"
                  @change="onFileInputChange"
                />
              </label>
            </div>
          </div>

          <input
            ref="cameraInputRef"
            type="file"
            accept="image/*,video/*"
            capture="environment"
            multiple
            class="hidden"
            @change="onFileInputChange"
          />

          <ul v-if="allFiles.length > 0" class="space-y-1 max-h-40 overflow-y-auto">
            <li
              v-for="(f, idx) in store.inFlightFilesByUser[user]"
              :key="`timer-${idx}-${f.name}`"
              class="text-xs flex items-center justify-between gap-2 py-1 px-2 bg-emerald-50 rounded"
            >
              <span class="truncate flex-1">
                <i class="pi pi-clock text-[10px] mr-1 text-emerald-700"></i>
                <span class="font-mono text-slate-700">{{ f.name }}</span>
                <span class="text-slate-500 ml-1">({{ Math.round(f.size / 1024) }} KB)</span>
                <span class="ml-1 text-[10px] uppercase text-emerald-700">timer</span>
              </span>
              <button type="button" class="text-rose-500 hover:text-rose-700" @click="removeFileFromTimer(idx)">
                <i class="pi pi-times text-xs"></i>
              </button>
            </li>
            <li
              v-for="(f, idx) in localFiles"
              :key="`local-${idx}-${f.name}`"
              class="text-xs flex items-center justify-between gap-2 py-1 px-2 bg-slate-50 rounded"
            >
              <span class="truncate flex-1">
                <i class="pi pi-file text-[10px] mr-1 text-slate-700"></i>
                <span class="font-mono text-slate-700">{{ f.name }}</span>
                <span class="text-slate-500 ml-1">({{ Math.round(f.size / 1024) }} KB)</span>
              </span>
              <button type="button" class="text-rose-500 hover:text-rose-700" @click="removeFileFromLocal(idx)">
                <i class="pi pi-times text-xs"></i>
              </button>
            </li>
          </ul>
          <div v-if="evidenceError" class="text-[11px] text-rose-600 mt-1">{{ evidenceError }}</div>
          <div v-if="allFiles.length === 0" class="text-[11px] text-slate-500 italic">
            Add photos/PDFs/videos. Each log gets its own GCS sub-folder; files are renamed
            <span class="font-mono">Property_Activity_YYYY-MM-DD_HHMM.ext</span> for the auditor.
          </div>
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
            :disabled="submitting || uploadingFiles"
            @click="close"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-2"
            :disabled="submitting || uploadingFiles || capturingSnapshot"
            @click="save"
          >
            <i v-if="submitting || uploadingFiles" class="pi pi-spin pi-spinner"></i>
            <span v-if="uploadingFiles">Uploading {{ allFiles.length }} file{{ allFiles.length === 1 ? '' : 's' }}...</span>
            <span v-else-if="submitting">Saving...</span>
            <span v-else>Save Entry</span>
          </button>
        </div>
      </footer>
    </div>
  </div>
</template>
