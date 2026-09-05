<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import api from '../../api';
import { useRepsStore, captureGeoSnapshot } from '../../stores/repsStore';
import {
  FALLBACK_REPS_ACTIVITY_CATEGORIES,
  type EvidenceItem,
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
// the modal here. Each file has a parallel `label` so the user can edit the
// short name shown in the Sheet's evidence cell (defaults to the filename
// without extension).
const localFiles = ref<File[]>([]);
const localLabels = ref<string[]>([]);
const timerLabels = ref<string[]>([]);
const evidenceError = ref('');

function deriveLabel(name: string): string {
  // Strip extension and any trailing audit-style timestamp/index suffix so
  // the user sees a clean default they're likely to keep ("Closing meeting"
  // over "ClosingMeeting_2026-05-03_1200").
  const stem = name.replace(/\.[^./\\]+$/, '');
  return stem.length > 80 ? stem.slice(0, 80) : stem;
}

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
// Order MUST match `allLabels` so we can zip URLs back to labels on save.
const allFiles = computed<File[]>(() => [
  ...store.inFlightFilesByUser[props.user],
  ...localFiles.value,
]);

const allLabels = computed<string[]>(() => [
  ...timerLabels.value,
  ...localLabels.value,
]);

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
  localLabels.value = [];
  // Seed timer-side labels from whatever the timer captured during clocking.
  timerLabels.value = store.inFlightFilesByUser[props.user].map(f => deriveLabel(f.name));
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
    localLabels.value = [...localLabels.value, ...accepted.map(f => deriveLabel(f.name))];
  }
}

function onFileInputChange(e: Event) {
  const input = e.target as HTMLInputElement;
  validateAndAcceptFiles(input.files);
  input.value = '';
}

function removeFileFromLocal(idx: number) {
  const files = [...localFiles.value];
  const labels = [...localLabels.value];
  files.splice(idx, 1);
  labels.splice(idx, 1);
  localFiles.value = files;
  localLabels.value = labels;
}

function removeFileFromTimer(idx: number) {
  // Keep `timerLabels` in lock-step with the store's queue so the zip on
  // save still maps each label to the right uploaded URL.
  const labels = [...timerLabels.value];
  labels.splice(idx, 1);
  timerLabels.value = labels;
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

  // Step 1: upload all queued files (no per-log folder anymore — they land
  // flat in the property's GCS directory), then zip the returned URLs back
  // to the user-supplied labels in input-order.
  let evidenceItems: EvidenceItem[] = [];
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
      const labels = allLabels.value;
      evidenceItems = batch.files.map((f, i) => ({
        url: f.url,
        label: (labels[i] || '').trim() || deriveLabel(f.name),
      }));
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
    evidence_items: evidenceItems,
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
    data-testid="repsmodal.root"
    class="fixed inset-0 z-50 flex items-center justify-center bg-fg/40 p-4 md:backdrop-blur-sm"
    @click.self="close"
  >
    <UiModalPanel size="lg" labelled-by="repsmodal-title">
      <template #header>
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h3 id="repsmodal-title" class="text-base font-semibold text-fg md:text-lg">
              New REPS Entry · {{ user }}
            </h3>
            <p class="mt-0.5 text-xs text-fg-muted">
              Total: <span class="font-semibold tabular text-fg">{{ totalHours.toFixed(2) }} h</span>
              · server stamps Created-At at save
            </p>
          </div>
          <UiIconButton data-testid="repsmodal.close" label="Close" size="md" @click="close">
            <i class="pi pi-times text-lg" aria-hidden="true"></i>
          </UiIconButton>
        </div>
      </template>

      <div class="space-y-4">
        <div
          v-if="formError"
          data-testid="repsmodal.error"
          class="rounded-ctl bg-negative/10 p-3 text-sm font-medium text-negative"
        >
          {{ formError }}
        </div>

        <!-- Property autocomplete -->
        <UiField class="relative">
          <template #label>Property Name</template>
          <template #default="{ id, describedBy }">
            <input
              data-testid="repsmodal.property-query"
              v-model="propertyQuery"
              :id="id"
              :aria-describedby="describedBy"
              type="text"
              placeholder="Type or pick a property... (e.g. 10th St, Honda, Galveston)"
              class="ui-input"
              role="combobox"
              aria-autocomplete="list"
              :aria-expanded="showPropertyDropdown"
              @focus="showPropertyDropdown = true"
              @input="propertyName = propertyQuery"
              @blur="onPropertyBlur"
            />
            <div
              v-if="showPropertyDropdown && (filteredProperties.length > 0 || (propertyQuery.trim() && !isExactMatch))"
              data-testid="repsmodal.property-dropdown"
              role="listbox"
              aria-label="Matching properties"
              class="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-ctl border border-line bg-surface shadow-2"
            >
              <button
                v-for="opt in filteredProperties"
                :key="opt.name"
                :data-testid="`repsmodal.property-option.${opt.name}`"
                type="button"
                role="option"
                :aria-selected="propertyName === opt.name"
                class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                @mousedown.prevent="pickProperty(opt.name)"
              >
                <span class="min-w-0 break-words text-sm text-fg">{{ opt.name }}</span>
                <UiBadge
                  class="shrink-0 uppercase"
                  :tone="opt.source === 'bought' ? 'positive' : 'warning'"
                >
                  {{ opt.source }}
                </UiBadge>
              </button>
              <div
                v-if="propertyQuery.trim() && !isExactMatch"
                role="presentation"
                class="border-t border-line px-3 py-2 text-xs italic text-fg-muted"
              >
                "{{ propertyQuery }}" will be saved to Prospects on submit.
              </div>
            </div>
          </template>
        </UiField>

        <!-- Activity category -->
        <div>
          <div class="mb-1 flex items-center justify-between gap-2">
            <label for="repsmodal-category" class="block text-sm font-medium text-fg">Activity Category</label>
            <UiButton
              type="button"
              data-testid="repsmodal.category-toggle"
              variant="ghost"
              size="sm"
              class="min-h-9 touch:min-h-11 text-[11px] text-primary"
              @click="showAddCategory = !showAddCategory"
            >
              <i class="pi pi-plus mr-1" aria-hidden="true"></i>{{ showAddCategory ? 'Cancel' : 'Add new' }}
            </UiButton>
          </div>
          <select
            data-testid="repsmodal.category-select"
            v-model="activityCategory"
            id="repsmodal-category"
            class="ui-select"
          >
            <option value="">— Select —</option>
            <option v-for="c in categoryOptions" :key="c" :data-testid="`repsmodal.category-option.${c}`" :value="c">{{ c }}</option>
          </select>
          <div v-if="showAddCategory" class="mt-2 flex gap-2">
            <input
              data-testid="repsmodal.category-name"
              v-model="newCategoryName"
              type="text"
              placeholder="New category name..."
              class="ui-input flex-1 text-sm"
              aria-label="New category name"
              @keyup.enter="addCategoryInline"
            />
            <UiButton
              type="button"
              data-testid="repsmodal.category-add"
              size="sm"
              class="min-h-9 touch:min-h-11 shrink-0"
              :disabled="addingCategory || !newCategoryName.trim()"
              @click="addCategoryInline"
            >
              <i v-if="addingCategory" class="pi pi-spin pi-spinner" aria-hidden="true"></i>
              <span v-else>Add</span>
            </UiButton>
          </div>
        </div>

        <!-- Description -->
        <UiField :invalid="descTooShort">
          <template #label>
            Description <span class="text-negative" aria-hidden="true">*</span>
            <span class="text-xs font-normal text-fg-muted">
              (≥ {{ MIN_DESC }} chars — be specific, e.g. "Met with Gilly at Honda to review plumbing")
            </span>
          </template>
          <template #default="{ id, describedBy, invalid }">
            <textarea
              data-testid="repsmodal.description"
              v-model="description"
              :id="id"
              :aria-describedby="describedBy"
              :aria-invalid="invalid"
              aria-required="true"
              rows="3"
              class="ui-textarea"
              :class="descTooShort ? 'ui-input-invalid' : ''"
            ></textarea>
            <div class="mt-1 text-[11px] tabular" :class="descTooShort ? 'text-negative' : 'text-positive'">
              <span v-if="descTooShort">{{ descRemaining }} more characters required</span>
              <span v-else>{{ description.trim().length }} chars</span>
            </div>
          </template>
        </UiField>

        <!-- Times -->
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <UiField>
            <template #label>Start Time <span class="text-negative" aria-hidden="true">*</span></template>
            <template #default="{ id, describedBy }">
              <input
                data-testid="repsmodal.start-time"
                v-model="startLocal"
                :id="id"
                :aria-describedby="describedBy"
                aria-required="true"
                type="datetime-local"
                class="ui-input"
              />
            </template>
          </UiField>
          <UiField>
            <template #label>End Time <span class="text-negative" aria-hidden="true">*</span></template>
            <template #default="{ id, describedBy }">
              <input
                data-testid="repsmodal.end-time"
                v-model="endLocal"
                :id="id"
                :aria-describedby="describedBy"
                aria-required="true"
                type="datetime-local"
                class="ui-input"
              />
            </template>
          </UiField>
        </div>

        <!-- Material participation -->
        <div class="rounded-ctl border border-line bg-surface-muted p-3">
          <label class="flex cursor-pointer items-start gap-2">
            <input
              data-testid="repsmodal.material-checkbox"
              v-model="materialParticipation"
              type="checkbox"
              class="mt-1 h-4 w-4 shrink-0 accent-primary"
            />
            <div>
              <div class="text-sm font-medium text-fg">
                Material Participation in rentals?
              </div>
              <div class="text-[11px] text-fg-muted">
                Counts toward the 500-hour material participation test (in addition to the 750-hour test).
              </div>
            </div>
          </label>
        </div>

        <!-- Location: GPS breadcrumbs + manual override.
             Capture is ALWAYS manual: nothing is recorded unless the user
             taps "Capture GPS now" or "Mark as Remote". -->
        <div class="rounded-ctl border border-line p-3">
          <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
            <label class="text-sm font-medium text-fg">
              Location · {{ allSnapshots.length }} GPS pin{{ allSnapshots.length === 1 ? '' : 's' }}
            </label>
            <div class="flex gap-2">
              <UiButton
                type="button"
                data-testid="repsmodal.capture-gps"
                variant="secondary"
                size="sm"
                class="min-h-9 touch:min-h-11"
                :disabled="capturingSnapshot"
                @click="captureSnapshotNow('manual_save')"
              >
                <i class="pi pi-map-marker text-[10px]" aria-hidden="true"></i>
                {{ capturingSnapshot ? 'Capturing...' : 'Capture GPS now' }}
              </UiButton>
              <UiButton
                type="button"
                data-testid="repsmodal.mark-remote"
                variant="ghost"
                size="sm"
                class="min-h-9 touch:min-h-11"
                @click="markRemote"
              >
                Mark as Remote
              </UiButton>
            </div>
          </div>

          <ul
            v-if="allSnapshots.length > 0"
            class="custom-scrollbar mb-2 max-h-32 space-y-1 overflow-y-auto overscroll-contain"
          >
            <li
              v-for="(s, idx) in allSnapshots"
              :key="idx"
              :data-testid="`repsmodal.snapshot.${idx}`"
              class="flex items-start justify-between gap-2 py-0.5 text-[11px] text-fg"
            >
              <span class="min-w-0 flex-1 break-words">
                <UiBadge tone="neutral" class="mr-1">{{ snapshotLabel(s) }}</UiBadge>
                <span v-if="s.lat != null && s.lng != null" class="tabular">
                  {{ s.lat.toFixed(5) }}, {{ s.lng.toFixed(5) }}<span v-if="s.accuracy_m"> (±{{ Math.round(s.accuracy_m) }}m)</span>
                </span>
                <span v-else class="text-fg-muted">[{{ s.note || 'no GPS' }}]</span>
                <a
                  v-if="snapshotMapHref(s)"
                  :data-testid="`repsmodal.snapshot.${idx}.map`"
                  :href="snapshotMapHref(s)!"
                  target="_blank"
                  class="ml-1 font-medium text-primary underline-offset-2 hover:underline"
                >map</a>
              </span>
              <!-- Only allow dropping breadcrumbs the modal added; timer-driven ones live in the store. -->
              <UiIconButton
                v-if="idx >= store.snapshotsByUser[user].length"
                type="button"
                :data-testid="`repsmodal.snapshot.${idx}.delete`"
                label="Remove location pin"
                variant="danger"
                @click="dropPendingSnapshot(idx - store.snapshotsByUser[user].length)"
              >
                <i class="pi pi-times text-xs" aria-hidden="true"></i>
              </UiIconButton>
            </li>
          </ul>
          <div v-else data-testid="repsmodal.snapshot-empty" class="mb-2 text-[11px] italic text-fg-muted">
            No location recorded yet. Tap "Capture GPS now" if you want to log
            where you are; otherwise leave the column blank or use the note
            below (e.g. "Remote — phone call").
          </div>

          <input
            data-testid="repsmodal.location-note"
            v-model="locationNote"
            type="text"
            placeholder="Optional note (e.g. 'Remote — phone call', 'Honda — 1234 Maple St')"
            class="ui-input text-sm"
            aria-label="Location note"
          />
        </div>

        <!-- Multi-asset evidence -->
        <div class="rounded-ctl border border-line p-3">
          <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
            <label class="text-sm font-medium text-fg">
              Evidence
              <UiBadge v-if="allFiles.length > 0" tone="primary" class="ml-1 tabular">
                {{ allFiles.length }} file{{ allFiles.length === 1 ? '' : 's' }} attached
              </UiBadge>
            </label>
            <div class="flex gap-2">
              <UiButton
                type="button"
                data-testid="repsmodal.evidence-camera"
                variant="secondary"
                size="sm"
                class="min-h-9 touch:min-h-11"
                @click="openCameraDirect"
              >
                <i class="pi pi-camera text-[10px]" aria-hidden="true"></i> Camera
              </UiButton>
              <label
                class="inline-flex min-h-9 touch:min-h-11 cursor-pointer items-center gap-1 rounded-ctl border border-line bg-surface px-2.5 py-1 text-xs font-medium text-fg transition-colors hover:bg-surface-muted focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2"
              >
                <i class="pi pi-paperclip text-[10px]" aria-hidden="true"></i> Attach
                <input
                  data-testid="repsmodal.file-input"
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
            data-testid="repsmodal.camera-input"
            type="file"
            accept="image/*,video/*"
            capture="environment"
            multiple
            class="hidden"
            @change="onFileInputChange"
          />

          <ul
            v-if="allFiles.length > 0"
            class="custom-scrollbar max-h-72 space-y-2 overflow-y-auto overscroll-contain"
          >
            <li
              v-for="(f, idx) in store.inFlightFilesByUser[user]"
              :key="`timer-${idx}-${f.name}`"
              :data-testid="`repsmodal.timer-file.${idx}`"
              class="rounded-ctl bg-positive/10 px-2 py-1.5 text-xs"
            >
              <div class="mb-1 flex items-center justify-between gap-2">
                <span class="min-w-0 flex-1 break-words">
                  <i class="pi pi-clock mr-1 text-[10px] text-positive" aria-hidden="true"></i>
                  <span class="tabular text-fg">{{ f.name }}</span>
                  <span class="ml-1 tabular text-fg-muted">({{ Math.round(f.size / 1024) }} KB)</span>
                  <span class="ml-1 text-[10px] uppercase text-positive">timer</span>
                </span>
                <UiIconButton
                  type="button"
                  :data-testid="`repsmodal.timer-file.${idx}.delete`"
                  label="Remove file"
                  variant="danger"
                  @click="removeFileFromTimer(idx)"
                >
                  <i class="pi pi-times text-xs" aria-hidden="true"></i>
                </UiIconButton>
              </div>
              <input
                :data-testid="`repsmodal.timer-file.${idx}.label`"
                v-model="timerLabels[idx]"
                type="text"
                placeholder="Short link name in the Sheet (e.g. 'Closing meeting photo')"
                maxlength="120"
                class="ui-input px-2 py-1 text-[11px]"
                aria-label="Evidence link name"
              />
            </li>
            <li
              v-for="(f, idx) in localFiles"
              :key="`local-${idx}-${f.name}`"
              :data-testid="`repsmodal.local-file.${idx}`"
              class="rounded-ctl bg-surface-muted px-2 py-1.5 text-xs"
            >
              <div class="mb-1 flex items-center justify-between gap-2">
                <span class="min-w-0 flex-1 break-words">
                  <i class="pi pi-file mr-1 text-[10px] text-fg-muted" aria-hidden="true"></i>
                  <span class="tabular text-fg">{{ f.name }}</span>
                  <span class="ml-1 tabular text-fg-muted">({{ Math.round(f.size / 1024) }} KB)</span>
                </span>
                <UiIconButton
                  type="button"
                  :data-testid="`repsmodal.local-file.${idx}.delete`"
                  label="Remove file"
                  variant="danger"
                  @click="removeFileFromLocal(idx)"
                >
                  <i class="pi pi-times text-xs" aria-hidden="true"></i>
                </UiIconButton>
              </div>
              <input
                :data-testid="`repsmodal.local-file.${idx}.label`"
                v-model="localLabels[idx]"
                type="text"
                placeholder="Short link name in the Sheet (e.g. 'Inspection report')"
                maxlength="120"
                class="ui-input px-2 py-1 text-[11px]"
                aria-label="Evidence link name"
              />
            </li>
          </ul>
          <div v-if="evidenceError" data-testid="repsmodal.evidence-error" class="mt-1 text-[11px] text-negative">{{ evidenceError }}</div>
          <div v-if="allFiles.length === 0" data-testid="repsmodal.evidence-empty" class="text-[11px] italic text-fg-muted">
            Add photos/PDFs/videos. Each file becomes a clickable named link in the Sheet's
            evidence column — type a short name once you've attached.
          </div>
        </div>

        <!-- People involved -->
        <div>
          <label class="mb-1 block text-sm font-medium text-fg">People Involved</label>
          <div v-if="store.people.length === 0" data-testid="repsmodal.people-empty" class="mb-2 text-xs text-fg-muted">
            No people yet. Add some on the People tab, or quick-add below.
          </div>
          <div v-else class="mb-2 flex flex-wrap gap-2">
            <UiButton
              v-for="p in store.people"
              :key="p.id"
              :data-testid="`repsmodal.person.${p.id}`"
              type="button"
              variant="secondary"
              size="sm"
              class="min-h-9 touch:min-h-11 rounded-full"
              :class="peopleSelected.has(p.name) ? 'border-primary bg-primary text-primary-fg hover:bg-primary-hover' : ''"
              :aria-pressed="peopleSelected.has(p.name)"
              @click="togglePerson(p.name)"
            >
              {{ p.name }}<span v-if="p.role" class="ml-1 opacity-75">· {{ p.role }}</span>
            </UiButton>
          </div>
          <div class="flex gap-2">
            <input
              data-testid="repsmodal.person-name"
              v-model="newPersonName"
              type="text"
              placeholder="Quick add a person..."
              class="ui-input flex-1 text-sm"
              aria-label="Quick add a person"
              @keyup.enter="quickAddPerson"
            />
            <UiIconButton
              type="button"
              data-testid="repsmodal.person-add"
              label="Add person"
              variant="secondary"
              size="md"
              @click="quickAddPerson"
            >
              <i class="pi pi-plus" aria-hidden="true"></i>
            </UiIconButton>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0 text-[11px] text-fg-muted">
            Once saved, this row is append-only — corrections must be a new entry.
          </div>
          <div class="flex shrink-0 gap-2">
            <UiButton
              type="button"
              data-testid="repsmodal.cancel"
              variant="ghost"
              :disabled="submitting || uploadingFiles"
              @click="close"
            >
              Cancel
            </UiButton>
            <UiButton
              type="button"
              data-testid="repsmodal.save"
              :disabled="submitting || uploadingFiles || capturingSnapshot"
              @click="save"
            >
              <i v-if="submitting || uploadingFiles" class="pi pi-spin pi-spinner" aria-hidden="true"></i>
              <span v-if="uploadingFiles">Uploading {{ allFiles.length }} file{{ allFiles.length === 1 ? '' : 's' }}...</span>
              <span v-else-if="submitting">Saving...</span>
              <span v-else>Save Entry</span>
            </UiButton>
          </div>
        </div>
      </template>
    </UiModalPanel>
  </div>
</template>
