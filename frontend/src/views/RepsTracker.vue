<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useRepsStore } from '../stores/repsStore';
import { REPS_USERS, REPS_USER_DISPLAY, type RepsUser } from '../types/reps';
import RepsTimer from '../components/reps/RepsTimer.vue';
import RepsEntryModal from '../components/reps/RepsEntryModal.vue';
import RepsStats from '../components/reps/RepsStats.vue';
import RepsEntriesList from '../components/reps/RepsEntriesList.vue';
import RepsPeopleManager from '../components/reps/RepsPeopleManager.vue';

const router = useRouter();
const store = useRepsStore();

const showModal = ref(false);
const modalInitialStart = ref<string | null>(null);
const modalInitialEnd = ref<string | null>(null);
const showPeoplePanel = ref(false);

const minDescLen = computed(() => store.configStatus?.min_description_length ?? 20);
const isConfigured = computed(() => store.configStatus?.configured ?? false);

const activeStats = computed(() => store.activeEntries?.stats ?? null);
const activeRows = computed(() => store.activeEntries?.entries ?? []);
const activeLoading = computed(() => store.loadingByUser[store.activeUser]);
const activeError = computed(() => store.errorByUser[store.activeUser]);

onMounted(async () => {
  await store.fetchConfigStatus();
  // Reference data — fire-and-forget; the modal also lazy-loads on open.
  store.fetchProperties().catch(() => {});
  store.fetchPeople().catch(() => {});
  if (isConfigured.value) {
    refreshActive();
  }
});

function setUser(u: RepsUser) {
  store.setActiveUser(u);
  if (isConfigured.value && !store.entriesByUser[u]) {
    store.fetchEntries(u);
  }
}

function refreshActive() {
  store.fetchEntries(store.activeUser);
}

function openManualEntry() {
  modalInitialStart.value = null;
  modalInitialEnd.value = null;
  showModal.value = true;
}

function onTimerFinish(payload: { startIso: string; endIso: string }) {
  modalInitialStart.value = payload.startIso;
  modalInitialEnd.value = payload.endIso;
  showModal.value = true;
}

function onSaved() {
  // Reset the timer for the active user once the entry is persisted.
  store.resetTimer(store.activeUser);
}
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-30">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button
            class="w-9 h-9 flex items-center justify-center rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            title="Back"
            @click="router.push('/')"
          >
            <i class="pi pi-arrow-left"></i>
          </button>
          <h1 class="text-xl font-bold text-slate-800 flex items-center gap-2">
            <i class="pi pi-clock text-blue-600"></i>
            REPS Tracker · 2026
          </h1>
        </div>
        <button
          class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          :class="showPeoplePanel ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'"
          @click="showPeoplePanel = !showPeoplePanel"
        >
          <i class="pi pi-users"></i> People
        </button>
      </div>

      <!-- Tabs -->
      <div class="max-w-6xl mx-auto px-4 flex items-end gap-1 -mb-px">
        <button
          v-for="u in REPS_USERS"
          :key="u"
          class="px-5 py-2.5 text-sm font-semibold border-b-2 transition-all flex items-center gap-2"
          :class="store.activeUser === u
            ? 'border-blue-600 text-blue-700'
            : 'border-transparent text-slate-500 hover:text-slate-700'"
          @click="setUser(u)"
        >
          <i class="pi pi-user text-xs"></i>
          {{ REPS_USER_DISPLAY[u] }}
          <span
            v-if="store.timers[u].running"
            class="ml-1 inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"
            title="Stopwatch running"
          ></span>
          <span
            v-else-if="store.timers[u].sessionStartedAt || store.timers[u].accumulatedMs > 0"
            class="ml-1 inline-block w-2 h-2 rounded-full bg-amber-400"
            title="Stopwatch paused"
          ></span>
        </button>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <!-- Config banner -->
      <div
        v-if="store.configStatus && !isConfigured"
        class="rounded-xl bg-amber-50 border border-amber-200 p-4 text-sm text-amber-800"
      >
        <div class="font-semibold mb-1 flex items-center gap-2">
          <i class="pi pi-exclamation-triangle"></i> REPS feature is not connected yet
        </div>
        <div class="text-amber-700">{{ store.configStatus.detail }}</div>
        <div class="text-amber-700 mt-1">
          See <code class="bg-amber-100 px-1 rounded">REPS_README.md</code> for setup instructions.
        </div>
      </div>

      <!-- Top row: timer + stats -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <RepsTimer :user="store.activeUser" @finish="onTimerFinish" />
        <div class="md:col-span-2">
          <RepsStats :stats="activeStats" :loading="activeLoading" />
        </div>
      </div>

      <!-- Action bar -->
      <div class="flex items-center justify-between">
        <div class="text-xs font-mono text-slate-500">
          Each entry is server-stamped at save time and appended to {{ store.activeUser }}'s sheet.
          <button
            class="ml-2 underline hover:text-slate-700"
            @click="refreshActive"
            :disabled="activeLoading"
          >
            Refresh
          </button>
        </div>
        <button
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold flex items-center gap-2 transition-colors"
          @click="openManualEntry"
        >
          <i class="pi pi-plus"></i> Manual Entry
        </button>
      </div>

      <!-- People panel (toggle) -->
      <RepsPeopleManager v-if="showPeoplePanel" />

      <!-- Entries list -->
      <RepsEntriesList
        :entries="activeRows"
        :loading="activeLoading"
        :error="activeError"
      />
    </main>

    <RepsEntryModal
      :open="showModal"
      :user="store.activeUser"
      :initial-start-iso="modalInitialStart"
      :initial-end-iso="modalInitialEnd"
      :min-description-length="minDescLen"
      @close="showModal = false"
      @saved="onSaved"
    />
  </div>
</template>
