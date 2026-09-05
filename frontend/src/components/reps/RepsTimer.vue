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
  <UiCard padding="none" class="h-full">
    <div class="flex h-full flex-col items-center gap-4 p-6">
      <div class="text-xs uppercase tracking-widest text-fg-muted">
        {{ user }} stopwatch
      </div>
      <div class="font-mono text-5xl font-bold tabular tracking-tight text-fg">
        {{ display }}
      </div>
      <div class="text-xs text-fg-muted">
        = {{ decimalHours.toFixed(2) }} h
        <span v-if="isRunning" class="ml-2 inline-flex items-center gap-1 text-positive">
          <span class="h-2 w-2 rounded-full bg-positive animate-pulse"></span> running
        </span>
        <span v-else-if="hasSession" class="ml-2 text-warning">paused</span>
      </div>

      <!-- Primary controls -->
      <div class="flex flex-wrap justify-center gap-2">
        <UiButton
          v-if="!hasSession"
          data-testid="repstimer.start"
          size="sm"
          class="min-h-11 px-3 shadow-1"
          @click="start"
        >
          <i class="pi pi-play" aria-hidden="true"></i> Start
        </UiButton>
        <UiButton
          v-else-if="isRunning"
          data-testid="repstimer.stop"
          variant="secondary"
          size="sm"
          class="min-h-11 border-warning/40 px-3 text-warning shadow-1 hover:bg-warning/10"
          @click="stop"
        >
          <i class="pi pi-pause" aria-hidden="true"></i> Stop
        </UiButton>
        <template v-else>
          <UiButton
            data-testid="repstimer.resume"
            size="sm"
            class="min-h-11 px-3 shadow-1"
            @click="resume"
          >
            <i class="pi pi-play" aria-hidden="true"></i> Resume
          </UiButton>
          <UiButton
            data-testid="repstimer.finish"
            variant="secondary"
            size="sm"
            class="min-h-11 border-positive/40 px-3 text-positive shadow-1 hover:bg-positive/10"
            @click="finish"
          >
            <i class="pi pi-check" aria-hidden="true"></i> Finish &amp; Log
          </UiButton>
          <UiIconButton
            data-testid="repstimer.discard"
            label="Discard session"
            variant="danger"
            size="md"
            class="self-center"
            @click="discard"
          >
            <i class="pi pi-trash" aria-hidden="true"></i>
          </UiIconButton>
        </template>
      </div>

      <!-- Live-session toolbar: explicit GPS capture + real-time camera/gallery.
           The "Pin GPS now" button is always visible while a session exists so
           the user can manually capture a snapshot at start, during, on pause,
           and right before finishing. We never auto-capture. -->
      <div v-if="hasSession" class="flex flex-wrap items-center justify-center gap-2 pt-1">
        <UiButton
          type="button"
          data-testid="repstimer.pin-gps"
          variant="secondary"
          size="sm"
          class="min-h-9"
          :disabled="capturing"
          :title="isRunning ? 'Capture GPS while clocked in' : 'Capture GPS at pause / before finish'"
          @click="pinGps(isRunning ? 'bookmark' : 'timer_pause')"
        >
          <i class="pi pi-map-marker" aria-hidden="true"></i>
          {{ capturing ? 'Capturing...' : 'Pin GPS now' }}
        </UiButton>
        <UiButton
          type="button"
          data-testid="repstimer.take-photo"
          variant="secondary"
          size="sm"
          class="min-h-9"
          @click="openCamera"
        >
          <i class="pi pi-camera" aria-hidden="true"></i> Take Photo / Video
        </UiButton>
        <UiButton
          type="button"
          data-testid="repstimer.attach-file"
          variant="secondary"
          size="sm"
          class="min-h-9"
          @click="openGallery"
        >
          <i class="pi pi-paperclip" aria-hidden="true"></i> Attach File
        </UiButton>
        <UiBadge v-if="inFlightFiles.length > 0" tone="primary" class="tabular">
          {{ inFlightFiles.length }} {{ inFlightFiles.length === 1 ? 'file' : 'files' }} queued
        </UiBadge>
        <UiBadge
          v-if="snapshots.length > 0"
          tone="positive"
          class="tabular"
          :title="lastSnapshot?.kind || ''"
        >
          {{ snapshots.length }} GPS pin{{ snapshots.length === 1 ? '' : 's' }}
        </UiBadge>
      </div>

      <input
        ref="cameraInput"
        data-testid="repstimer.camera-input"
        type="file"
        accept="image/*,video/*"
        capture="environment"
        class="hidden"
        multiple
        @change="onCameraFiles"
      />
      <input
        ref="galleryInput"
        data-testid="repstimer.gallery-input"
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.mov,.mp4"
        class="hidden"
        multiple
        @change="onCameraFiles"
      />

      <div v-if="hasSession" class="mt-auto text-center text-[11px] text-fg-muted">
        Session started:
        {{ timer.sessionStartedAt ? new Date(timer.sessionStartedAt).toLocaleString() : '—' }}
      </div>
    </div>
  </UiCard>
</template>
