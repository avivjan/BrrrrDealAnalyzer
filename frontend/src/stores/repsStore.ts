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
} from '../types/reps';

// Tip from the spec: each user has a unique key in localStorage so that
// switching tabs never resets the inactive user's stopwatch.
const TIMER_STORAGE_KEY: Record<RepsUser, string> = {
  Aviv2026: 'timer_state_aviv',
  Yarden2026: 'timer_state_yarden',
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

  function _save(user: RepsUser) {
    persistTimerState(user, { ...timers[user] });
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

  return {
    activeUser,
    setActiveUser,
    timers,
    startTimer,
    stopTimer,
    resumeTimer,
    resetTimer,
    elapsedMs,
    elapsedHours,
    configStatus,
    properties,
    people,
    entriesByUser,
    activeEntries,
    loadingByUser,
    errorByUser,
    fetchConfigStatus,
    fetchEntries,
    fetchProperties,
    fetchPeople,
    addPerson,
    updatePerson,
    removePerson,
    ensureProspect,
  };
});
