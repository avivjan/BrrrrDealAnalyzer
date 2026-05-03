import { defineStore } from 'pinia';
import { ref, computed, reactive } from 'vue';
import api from '../api';
import {
  EMPTY_REPS_TIMER_STATE,
  REPS_USERS,
  type RepsConfigStatus,
  type RepsEntriesEnvelope,
  type RepsPerson,
  type RepsPropertyOption,
  type RepsTimerState,
  type RepsUser,
  type LocationSnapshot,
  type LocationSnapshotKind,
  type RepsActivityCategoryRes,
} from '../types/reps';

// Tip from the spec: each user has a unique key in localStorage so that
// switching tabs never resets the inactive user's stopwatch.
const TIMER_STORAGE_KEY: Record<RepsUser, string> = {
  Aviv2026: 'timer_state_aviv',
  Yarden2026: 'timer_state_yarden',
};

// Per-user breadcrumb buffer; survives refresh so a captured START isn't lost.
const SNAPSHOTS_STORAGE_KEY: Record<RepsUser, string> = {
  Aviv2026: 'reps_snapshots_aviv',
  Yarden2026: 'reps_snapshots_yarden',
};

const ACTIVE_TAB_STORAGE_KEY = 'reps_active_tab';

function loadTimerState(user: RepsUser): RepsTimerState {
  try {
    const raw = localStorage.getItem(TIMER_STORAGE_KEY[user]);
    if (!raw) return { ...EMPTY_REPS_TIMER_STATE };
    const parsed = JSON.parse(raw) as Partial<RepsTimerState>;
    return {
      startedAt: parsed.startedAt ?? null,
      accumulatedMs: typeof parsed.accumulatedMs === 'number' ? parsed.accumulatedMs : 0,
      sessionStartedAt: parsed.sessionStartedAt ?? null,
      running: !!parsed.running,
    };
  } catch (err) {
    console.warn('repsStore: failed to load timer state for', user, err);
    return { ...EMPTY_REPS_TIMER_STATE };
  }
}

function persistTimerState(user: RepsUser, state: RepsTimerState) {
  try {
    localStorage.setItem(TIMER_STORAGE_KEY[user], JSON.stringify(state));
  } catch (err) {
    console.warn('repsStore: failed to persist timer state for', user, err);
  }
}

function loadSnapshots(user: RepsUser): LocationSnapshot[] {
  try {
    const raw = localStorage.getItem(SNAPSHOTS_STORAGE_KEY[user]);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as LocationSnapshot[]) : [];
  } catch (err) {
    console.warn('repsStore: failed to load snapshots for', user, err);
    return [];
  }
}

function persistSnapshots(user: RepsUser, snaps: LocationSnapshot[]) {
  try {
    localStorage.setItem(SNAPSHOTS_STORAGE_KEY[user], JSON.stringify(snaps));
  } catch (err) {
    console.warn('repsStore: failed to persist snapshots for', user, err);
  }
}

/**
 * Wrap navigator.geolocation.getCurrentPosition in a single Promise.
 * Resolves with a snapshot regardless of success: GPS coords on permission
 * grant, otherwise a snapshot with `note: <reason>` so the audit trail is
 * still complete (an entry that says "permission_denied" is more honest than
 * silently dropping the breadcrumb).
 */
export async function captureGeoSnapshot(
  kind: LocationSnapshotKind,
  noteOnFailure?: string,
  options: PositionOptions = { enableHighAccuracy: true, timeout: 8000, maximumAge: 30000 },
): Promise<LocationSnapshot> {
  const captured_at = new Date().toISOString();

  if (typeof navigator === 'undefined' || !('geolocation' in navigator)) {
    return { kind, captured_at, note: noteOnFailure || 'unsupported' };
  }

  return new Promise(resolve => {
    let settled = false;
    const settle = (snap: LocationSnapshot) => {
      if (!settled) {
        settled = true;
        resolve(snap);
      }
    };

    try {
      navigator.geolocation.getCurrentPosition(
        pos => {
          settle({
            kind,
            captured_at,
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy_m: pos.coords.accuracy,
          });
        },
        err => {
          let why = 'unknown_error';
          if (err.code === err.PERMISSION_DENIED) why = 'permission_denied';
          else if (err.code === err.POSITION_UNAVAILABLE) why = 'position_unavailable';
          else if (err.code === err.TIMEOUT) why = 'timeout';
          settle({ kind, captured_at, note: noteOnFailure || why });
        },
        options,
      );
    } catch (err) {
      console.warn('captureGeoSnapshot: threw', err);
      settle({ kind, captured_at, note: noteOnFailure || 'exception' });
    }
  });
}

export const useRepsStore = defineStore('reps', () => {
  // --- Active tab (persisted) --- //
  const initialActive: RepsUser =
    (localStorage.getItem(ACTIVE_TAB_STORAGE_KEY) as RepsUser) || 'Aviv2026';
  const activeUser = ref<RepsUser>(REPS_USERS.includes(initialActive) ? initialActive : 'Aviv2026');

  function setActiveUser(u: RepsUser) {
    activeUser.value = u;
    try {
      localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, u);
    } catch {
      // non-fatal
    }
  }

  // --- Timer state per user (independent, persisted) --- //
  const timers = reactive<Record<RepsUser, RepsTimerState>>({
    Aviv2026: loadTimerState('Aviv2026'),
    Yarden2026: loadTimerState('Yarden2026'),
  });

  // Per-user buffered location breadcrumbs + in-flight evidence files captured
  // during the current session. Both are persisted; `inFlightFiles` only stores
  // metadata in localStorage (Files themselves don't survive refresh).
  const snapshotsByUser = reactive<Record<RepsUser, LocationSnapshot[]>>({
    Aviv2026: loadSnapshots('Aviv2026'),
    Yarden2026: loadSnapshots('Yarden2026'),
  });

  // Captured in-memory only; cleared on resetTimer(). Each entry is a real
  // browser File object queued for upload at "Save".
  const inFlightFilesByUser = reactive<Record<RepsUser, File[]>>({
    Aviv2026: [],
    Yarden2026: [],
  });

  function _save(user: RepsUser) {
    persistTimerState(user, { ...timers[user] });
  }

  function _saveSnaps(user: RepsUser) {
    persistSnapshots(user, snapshotsByUser[user]);
  }

  function pushSnapshot(user: RepsUser, snap: LocationSnapshot) {
    snapshotsByUser[user] = [...snapshotsByUser[user], snap];
    _saveSnaps(user);
  }

  function clearSnapshots(user: RepsUser) {
    snapshotsByUser[user] = [];
    _saveSnaps(user);
  }

  /**
   * Capture a GPS reading at the moment of `kind` and append it to this user's
   * snapshot buffer. Safe to await — never throws (snapshots have a `note`
   * fallback if the browser can't get a reading).
   */
  async function captureAndPushSnapshot(
    user: RepsUser,
    kind: LocationSnapshotKind,
    noteOnFailure?: string,
  ): Promise<LocationSnapshot> {
    const snap = await captureGeoSnapshot(kind, noteOnFailure);
    pushSnapshot(user, snap);
    return snap;
  }

  function addInFlightFile(user: RepsUser, file: File) {
    inFlightFilesByUser[user] = [...inFlightFilesByUser[user], file];
  }

  function removeInFlightFile(user: RepsUser, idx: number) {
    const list = [...inFlightFilesByUser[user]];
    list.splice(idx, 1);
    inFlightFilesByUser[user] = list;
  }

  function clearInFlightFiles(user: RepsUser) {
    inFlightFilesByUser[user] = [];
  }

  function startTimer(user: RepsUser) {
    const t = timers[user];
    if (t.running) return;
    const nowIso = new Date().toISOString();
    t.startedAt = nowIso;
    if (!t.sessionStartedAt) t.sessionStartedAt = nowIso;
    t.running = true;
    _save(user);
  }

  function stopTimer(user: RepsUser) {
    const t = timers[user];
    if (!t.running || !t.startedAt) return;
    const segmentMs = Math.max(0, Date.now() - new Date(t.startedAt).getTime());
    t.accumulatedMs += segmentMs;
    t.startedAt = null;
    t.running = false;
    _save(user);
  }

  function resumeTimer(user: RepsUser) {
    // Same as start but preserves sessionStartedAt.
    startTimer(user);
  }

  function resetTimer(user: RepsUser) {
    timers[user] = { ...EMPTY_REPS_TIMER_STATE };
    _save(user);
    clearSnapshots(user);
    clearInFlightFiles(user);
  }

  function elapsedMs(user: RepsUser, nowMs: number = Date.now()): number {
    const t = timers[user];
    let total = t.accumulatedMs;
    if (t.running && t.startedAt) {
      total += Math.max(0, nowMs - new Date(t.startedAt).getTime());
    }
    return total;
  }

  function elapsedHours(user: RepsUser, nowMs: number = Date.now()): number {
    return Math.round((elapsedMs(user, nowMs) / 3_600_000) * 100) / 100;
  }

  // --- Server-backed state --- //
  const configStatus = ref<RepsConfigStatus | null>(null);
  const properties = ref<RepsPropertyOption[]>([]);
  const people = ref<RepsPerson[]>([]);
  const activityCategories = ref<RepsActivityCategoryRes[]>([]);
  const entriesByUser = reactive<Record<RepsUser, RepsEntriesEnvelope | null>>({
    Aviv2026: null,
    Yarden2026: null,
  });
  const loadingByUser = reactive<Record<RepsUser, boolean>>({
    Aviv2026: false,
    Yarden2026: false,
  });
  const errorByUser = reactive<Record<RepsUser, string | null>>({
    Aviv2026: null,
    Yarden2026: null,
  });

  const activeEntries = computed(() => entriesByUser[activeUser.value]);

  async function fetchConfigStatus() {
    try {
      configStatus.value = await api.getRepsConfigStatus();
    } catch (err: any) {
      configStatus.value = {
        configured: false,
        detail: err?.message || 'Could not reach server',
        min_description_length: 20,
      };
    }
  }

  async function fetchEntries(user: RepsUser) {
    loadingByUser[user] = true;
    errorByUser[user] = null;
    try {
      entriesByUser[user] = await api.getRepsEntries(user);
    } catch (err: any) {
      errorByUser[user] = err?.response?.data?.detail || err?.message || 'Failed to load entries';
    } finally {
      loadingByUser[user] = false;
    }
  }

  async function fetchProperties() {
    properties.value = await api.getRepsProperties();
  }

  async function fetchPeople() {
    people.value = await api.getRepsPeople();
  }

  async function addPerson(payload: { name: string; role?: string; notes?: string }) {
    const person = await api.createRepsPerson(payload);
    people.value = [...people.value, person].sort((a, b) => a.name.localeCompare(b.name));
    return person;
  }

  async function updatePerson(id: string, payload: { name?: string; role?: string; notes?: string }) {
    const person = await api.updateRepsPerson(id, payload);
    const idx = people.value.findIndex(p => p.id === id);
    if (idx >= 0) people.value[idx] = person;
    return person;
  }

  async function removePerson(id: string) {
    await api.deleteRepsPerson(id);
    people.value = people.value.filter(p => p.id !== id);
  }

  async function ensureProspect(name: string) {
    const trimmed = name.trim();
    if (!trimmed) return null;
    const exists = properties.value.some(p => p.name.toLowerCase() === trimmed.toLowerCase());
    if (exists) return properties.value.find(p => p.name.toLowerCase() === trimmed.toLowerCase()) ?? null;
    const created = await api.createRepsProspect(trimmed);
    properties.value = [...properties.value, created];
    return created;
  }

  async function fetchActivityCategories() {
    activityCategories.value = await api.getRepsActivityCategories();
  }

  async function addActivityCategory(name: string) {
    const trimmed = name.trim();
    if (!trimmed) return null;
    const existing = activityCategories.value.find(
      c => c.name.toLowerCase() === trimmed.toLowerCase(),
    );
    if (existing) return existing;
    const created = await api.createRepsActivityCategory(trimmed);
    // Insert sorted (server returns sort_order); rely on a re-sort on read.
    activityCategories.value = [...activityCategories.value, created].sort(
      (a, b) =>
        (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.name.localeCompare(b.name),
    );
    return created;
  }

  async function deleteActivityCategory(id: string) {
    await api.deleteRepsActivityCategory(id);
    activityCategories.value = activityCategories.value.filter(c => c.id !== id);
  }

  return {
    activeUser,
    setActiveUser,
    timers,
    snapshotsByUser,
    inFlightFilesByUser,
    pushSnapshot,
    clearSnapshots,
    captureAndPushSnapshot,
    addInFlightFile,
    removeInFlightFile,
    clearInFlightFiles,
    startTimer,
    stopTimer,
    resumeTimer,
    resetTimer,
    elapsedMs,
    elapsedHours,
    configStatus,
    properties,
    people,
    activityCategories,
    entriesByUser,
    activeEntries,
    loadingByUser,
    errorByUser,
    fetchConfigStatus,
    fetchEntries,
    fetchProperties,
    fetchPeople,
    fetchActivityCategories,
    addActivityCategory,
    deleteActivityCategory,
    addPerson,
    updatePerson,
    removePerson,
    ensureProspect,
  };
});
