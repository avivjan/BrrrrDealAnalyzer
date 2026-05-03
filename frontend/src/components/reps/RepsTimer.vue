<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRepsStore } from '../../stores/repsStore';
import type { RepsUser } from '../../types/reps';

const props = defineProps<{
  user: RepsUser;
}>();

const emit = defineEmits<{
  (e: 'finish', payload: { startIso: string; endIso: string; totalHours: number }): void;
}>();

const store = useRepsStore();

// Re-render every second so the on-screen elapsed counter ticks even when the
// store state hasn't changed (it only changes on start/stop).
const tick = ref(Date.now());
let intervalId: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  intervalId = setInterval(() => {
    tick.value = Date.now();
  }, 1000);
});
onBeforeUnmount(() => {
  if (intervalId) clearInterval(intervalId);
});

const timer = computed(() => store.timers[props.user]);
const isRunning = computed(() => timer.value.running);
const hasSession = computed(() => !!timer.value.sessionStartedAt || timer.value.accumulatedMs > 0 || isRunning.value);

const elapsedMs = computed(() => store.elapsedMs(props.user, tick.value));

const display = computed(() => {
  const totalSec = Math.floor(elapsedMs.value / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return [h, m, s].map(n => String(n).padStart(2, '0')).join(':');
});

const decimalHours = computed(() => Math.round((elapsedMs.value / 3_600_000) * 100) / 100);

// Per-user buffers exposed by the store. Reading them through the store keeps
// reactivity intact when switching tabs.
const snapshots = computed(() => store.snapshotsByUser[props.user]);
const inFlightFiles = computed(() => store.inFlightFilesByUser[props.user]);

const lastSnapshot = computed(() => snapshots.value[snapshots.value.length - 1]);
const capturing = ref(false);
const cameraInput = ref<HTMLInputElement | null>(null);
const galleryInput = ref<HTMLInputElement | null>(null);

function start() {
  store.startTimer(props.user);
}

function stop() {
  // Stop pauses the segment but keeps sessionStartedAt + accumulated so the
  // user can resume or finalize. The user may now click "Pin GPS" to record
  // a pause-time location if they want one.
  store.stopTimer(props.user);
}

function resume() {
  store.resumeTimer(props.user);
}

async function pinGps(kind: 'bookmark' | 'timer_pause' | 'timer_resume' | 'timer_stop' | 'timer_start' = 'bookmark') {
  // The single, explicit "capture-my-current-location" button. The `kind`
  // parameter just labels the breadcrumb in the audit trail; we default to
  // a generic `bookmark` so a single tap does the right thing in any state.
  capturing.value = true;
  try {
    await store.captureAndPushSnapshot(props.user, kind);
  } finally {
    capturing.value = false;
  }
}

function finish() {
  if (timer.value.running) {
    store.stopTimer(props.user);
  }
  const start = timer.value.sessionStartedAt;
  const end = new Date().toISOString();
  if (!start) return;
  const totalHours = Math.round((timer.value.accumulatedMs / 3_600_000) * 100) / 100;
  emit('finish', { startIso: start, endIso: end, totalHours });
}

function discard() {
  if (!confirm('Discard this stopwatch session? Timer, GPS breadcrumbs, and queued evidence will reset.')) return;
  store.resetTimer(props.user);
}

// --- Real-time camera / file capture during an active session --- //

function openCamera() {
  cameraInput.value?.click();
}

function openGallery() {
  galleryInput.value?.click();
}

function onCameraFiles(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  for (const f of files) {
    store.addInFlightFile(props.user, f);
  }
  input.value = '';
}
</script>

<template>
  <div class="rounded-2xl border border-slate-200 bg-white shadow-sm p-6 flex flex-col items-center gap-4">
    <div class="text-xs font-mono uppercase tracking-widest text-slate-500">
      {{ user }} stopwatch
    </div>
    <div class="font-mono font-bold text-5xl tabular-nums tracking-tight text-slate-800">
      {{ display }}
    </div>
    <div class="text-xs font-mono text-slate-500">
      = {{ decimalHours.toFixed(2) }} h
      <span v-if="isRunning" class="ml-2 inline-flex items-center gap-1 text-emerald-600">
        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> running
      </span>
      <span v-else-if="hasSession" class="ml-2 text-amber-600">paused</span>
    </div>

    <!-- Primary controls -->
    <div class="flex flex-wrap gap-2 justify-center">
      <button
        v-if="!hasSession"
        class="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg shadow-sm transition-colors flex items-center gap-2"
        @click="start"
      >
        <i class="pi pi-play"></i> Start
      </button>
      <button
        v-else-if="isRunning"
        class="px-5 py-2 bg-amber-500 hover:bg-amber-600 text-white font-semibold rounded-lg shadow-sm transition-colors flex items-center gap-2"
        @click="stop"
      >
        <i class="pi pi-pause"></i> Stop
      </button>
      <template v-else>
        <button
          class="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg shadow-sm transition-colors flex items-center gap-2"
          @click="resume"
        >
          <i class="pi pi-play"></i> Resume
        </button>
        <button
          class="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-sm transition-colors flex items-center gap-2"
          @click="finish"
        >
          <i class="pi pi-check"></i> Finish &amp; Log
        </button>
        <button
          class="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors flex items-center gap-2"
          @click="discard"
        >
          <i class="pi pi-trash"></i>
        </button>
      </template>
    </div>

    <!-- Live-session toolbar: explicit GPS capture + real-time camera/gallery.
         The "Pin GPS now" button is always visible while a session exists so
         the user can manually capture a snapshot at start, during, on pause,
         and right before finishing. We never auto-capture. -->
    <div v-if="hasSession" class="flex flex-wrap items-center gap-2 justify-center pt-1">
      <button
        type="button"
        class="px-3 py-1.5 text-xs bg-indigo-100 text-indigo-700 hover:bg-indigo-200 rounded-lg flex items-center gap-1.5 disabled:opacity-50"
        :disabled="capturing"
        :title="isRunning ? 'Capture GPS while clocked in' : 'Capture GPS at pause / before finish'"
        @click="pinGps(isRunning ? 'bookmark' : 'timer_pause')"
      >
        <i class="pi pi-map-marker"></i>
        {{ capturing ? 'Capturing...' : 'Pin GPS now' }}
      </button>
      <button
        type="button"
        class="px-3 py-1.5 text-xs bg-rose-100 text-rose-700 hover:bg-rose-200 rounded-lg flex items-center gap-1.5"
        @click="openCamera"
      >
        <i class="pi pi-camera"></i> Take Photo / Video
      </button>
      <button
        type="button"
        class="px-3 py-1.5 text-xs bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-lg flex items-center gap-1.5"
        @click="openGallery"
      >
        <i class="pi pi-paperclip"></i> Attach File
      </button>
      <span
        v-if="inFlightFiles.length > 0"
        class="text-[11px] font-mono text-slate-600 px-2 py-0.5 rounded-full bg-blue-100 text-blue-700"
      >
        {{ inFlightFiles.length }} {{ inFlightFiles.length === 1 ? 'file' : 'files' }} queued
      </span>
      <span
        v-if="snapshots.length > 0"
        class="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700"
        :title="lastSnapshot?.kind || ''"
      >
        {{ snapshots.length }} GPS pin{{ snapshots.length === 1 ? '' : 's' }}
      </span>
    </div>

    <input
      ref="cameraInput"
      type="file"
      accept="image/*,video/*"
      capture="environment"
      class="hidden"
      multiple
      @change="onCameraFiles"
    />
    <input
      ref="galleryInput"
      type="file"
      accept=".pdf,.jpg,.jpeg,.png,.mov,.mp4"
      class="hidden"
      multiple
      @change="onCameraFiles"
    />

    <div v-if="hasSession" class="text-[11px] font-mono text-slate-400 text-center">
      Session started:
      {{ timer.sessionStartedAt ? new Date(timer.sessionStartedAt).toLocaleString() : '—' }}
    </div>
  </div>
</template>
