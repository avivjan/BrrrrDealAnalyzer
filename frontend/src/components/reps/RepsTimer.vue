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

function start() {
  store.startTimer(props.user);
}

function stop() {
  // Stop pauses the segment but keeps sessionStartedAt + accumulated so the
  // user can resume or finalize.
  store.stopTimer(props.user);
}

function resume() {
  store.resumeTimer(props.user);
}

function finish() {
  // Make sure we capture any in-flight running segment first.
  if (timer.value.running) {
    store.stopTimer(props.user);
  }
  const start = timer.value.sessionStartedAt;
  const end = new Date().toISOString();
  if (!start) return;
  // Use the *accumulated* hours for total, not wall-clock end-start, so that
  // stop/resume gaps don't inflate the audit total.
  const totalHours = Math.round((timer.value.accumulatedMs / 3_600_000) * 100) / 100;
  emit('finish', { startIso: start, endIso: end, totalHours });
}

function discard() {
  if (!confirm('Discard this stopwatch session? The timer will reset.')) return;
  store.resetTimer(props.user);
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

    <div v-if="hasSession" class="text-[11px] font-mono text-slate-400">
      Session started:
      {{ timer.sessionStartedAt ? new Date(timer.sessionStartedAt).toLocaleString() : '—' }}
    </div>
  </div>
</template>
