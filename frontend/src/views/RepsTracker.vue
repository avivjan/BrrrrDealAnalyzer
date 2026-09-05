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
  <div class="min-h-dvh bg-page pb-safe-b">
    <!-- Header -->
    <header class="sticky top-0 z-30 border-b border-line bg-surface">
      <div class="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
        <div class="flex min-w-0 items-center gap-3">
          <UiIconButton
            data-testid="reps.back"
            label="Back"
            size="md"
            title="Back"
            @click="router.push('/')"
          >
            <i class="pi pi-arrow-left" aria-hidden="true"></i>
          </UiIconButton>
          <h1 class="flex min-w-0 items-center gap-2 text-lg font-bold tracking-tight text-fg md:text-xl">
            <i class="pi pi-clock text-primary" aria-hidden="true"></i>
            REPS Tracker · 2026
          </h1>
        </div>
        <UiButton
          data-testid="reps.people-toggle"
          :variant="showPeoplePanel ? 'primary' : 'secondary'"
          size="sm"
          class="min-h-9 shrink-0"
          @click="showPeoplePanel = !showPeoplePanel"
        >
          <i class="pi pi-users" aria-hidden="true"></i> People
        </UiButton>
      </div>

      <!-- Tabs -->
      <div class="mx-auto max-w-6xl px-4 pb-3">
        <UiTabs aria-label="REPS user" class="max-w-full">
          <UiButton
            v-for="u in REPS_USERS"
            :key="u"
            :data-testid="`reps.tab.${u}`"
            variant="tab"
            size="sm"
            :active="store.activeUser === u"
            class="min-h-9 shrink-0"
            @click="setUser(u)"
          >
            <i class="pi pi-user text-xs" aria-hidden="true"></i>
            {{ REPS_USER_DISPLAY[u] }}
            <span
              v-if="store.timers[u].running"
              class="ml-1 inline-block h-2 w-2 shrink-0 rounded-full bg-positive animate-pulse"
              title="Stopwatch running"
            ></span>
            <span
              v-else-if="store.timers[u].sessionStartedAt || store.timers[u].accumulatedMs > 0"
              class="ml-1 inline-block h-2 w-2 shrink-0 rounded-full bg-warning"
              title="Stopwatch paused"
            ></span>
          </UiButton>
        </UiTabs>
      </div>
    </header>

    <main class="mx-auto max-w-6xl space-y-6 px-4 py-6">
      <!-- Config banner -->
      <div
        v-if="store.configStatus && !isConfigured"
        data-testid="reps.config-banner"
        class="rounded-card border border-warning/40 bg-warning/10 p-4 text-sm text-fg"
      >
        <div class="mb-1 flex items-center gap-2 font-semibold">
          <i class="pi pi-exclamation-triangle text-warning" aria-hidden="true"></i> REPS feature is not connected yet
        </div>
        <div class="text-fg-muted">{{ store.configStatus.detail }}</div>
        <div class="mt-1 text-fg-muted">
          See <code class="rounded-ctl bg-warning/20 px-1 tabular">REPS_README.md</code> for setup instructions.
        </div>
      </div>

      <!-- Top row: timer + stats -->
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3 md:gap-6">
        <RepsTimer :user="store.activeUser" @finish="onTimerFinish" />
        <div class="md:col-span-2">
          <RepsStats :stats="activeStats" :loading="activeLoading" />
        </div>
      </div>

      <!-- Action bar -->
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0 text-xs text-fg-muted">
          Each entry is server-stamped at save time and appended to {{ store.activeUser }}'s sheet.
          <UiButton
            data-testid="reps.refresh"
            variant="ghost"
            size="sm"
            class="ml-2 min-h-9 underline"
            @click="refreshActive"
            :loading="activeLoading"
            :disabled="activeLoading"
          >
            Refresh
          </UiButton>
        </div>
        <UiButton
          data-testid="reps.manual-entry"
          class="shrink-0 font-semibold shadow-2"
          @click="openManualEntry"
        >
          <i class="pi pi-plus" aria-hidden="true"></i> Manual Entry
        </UiButton>
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
