<script setup lang="ts">
/**
 * Hover/tap reveal for a single metric's calculation breakdown.
 *
 * Renders a small info icon next to the label. On desktop, hovering the icon
 * shows the steps; on touch screens, tapping toggles the popover. The steps
 * come straight from `BrrrAnalyzeRes.breakdowns[metricKey]` (or Flip), so the
 * UI is always in sync with the backend math without recomputing anything.
 */
import { computed, onBeforeUnmount, ref } from "vue";
import type { CalcStep } from "../../types";

const props = withDefaults(
  defineProps<{
    /** Steps to display, in derivation order. */
    steps?: CalcStep[];
    /** Title shown at the top of the tooltip (defaults to "Calculation"). */
    title?: string;
    /** Optional accent color (Tailwind text-* class). */
    accentClass?: string;
  }>(),
  {
    steps: () => [],
    title: "How this is calculated",
    accentClass: "text-blue-600",
  },
);

const open = ref(false);
const wrapper = ref<HTMLElement | null>(null);

const hasSteps = computed(() => (props.steps?.length ?? 0) > 0);

const formatValue = (v: number): string => {
  if (v === -1) return "∞";
  if (v === -2) return "-∞";
  // Heuristic: percentages tend to live in [-200, 200]; if the absolute value
  // is "small" treat it as a number/percent and avoid the $ prefix. Otherwise
  // format as currency. Steps always include the unit in the formula text, so
  // this is just a hint for the trailing value badge.
  const abs = Math.abs(v);
  if (abs < 1000 && !Number.isInteger(v)) {
    return v.toFixed(2);
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: abs < 1000 ? 2 : 0,
  }).format(v);
};

const toggle = (e: Event) => {
  e.stopPropagation();
  open.value = !open.value;
};

const onDocClick = (e: MouseEvent) => {
  if (!wrapper.value) return;
  if (!wrapper.value.contains(e.target as Node)) open.value = false;
};

if (typeof document !== "undefined") {
  document.addEventListener("click", onDocClick);
  onBeforeUnmount(() => document.removeEventListener("click", onDocClick));
}
</script>

<template>
  <span
    ref="wrapper"
    class="relative inline-flex items-center group"
    @mouseenter="open = true"
    @mouseleave="open = false"
  >
    <button
      type="button"
      class="inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold transition-colors"
      :class="[
        accentClass,
        'bg-white/0 hover:bg-current/10 border border-current/30 hover:border-current/60',
      ]"
      :aria-label="title"
      :aria-expanded="open"
      @click="toggle"
    >
      <i class="pi pi-info-circle text-[11px]"></i>
    </button>

    <transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-1"
    >
      <div
        v-if="open && hasSteps"
        class="absolute z-50 left-1/2 -translate-x-1/2 top-full mt-2 w-[20rem] sm:w-[24rem] max-w-[calc(100vw-2rem)] bg-white border border-gray-200 rounded-xl shadow-2xl p-3 text-left"
        @click.stop
      >
        <div class="flex items-start justify-between mb-2">
          <h4 class="text-xs font-bold uppercase tracking-wider text-gray-500">
            {{ title }}
          </h4>
          <button
            class="md:hidden text-gray-400 hover:text-gray-600"
            @click="open = false"
            aria-label="Close"
          >
            <i class="pi pi-times text-[10px]"></i>
          </button>
        </div>

        <ol class="space-y-2">
          <li
            v-for="(step, idx) in steps"
            :key="idx"
            class="text-[12px] leading-snug"
          >
            <div class="flex items-baseline justify-between gap-2">
              <span class="font-semibold text-gray-800">{{ step.label }}</span>
              <span
                class="font-mono text-[11px] tabular-nums"
                :class="accentClass"
              >
                {{ formatValue(step.value) }}
              </span>
            </div>
            <div class="text-gray-500 font-mono text-[11px] mt-0.5">
              {{ step.formula }}
            </div>
            <div
              v-if="idx < steps.length - 1"
              class="border-t border-dashed border-gray-100 mt-2"
            ></div>
          </li>
        </ol>

        <div class="text-[10px] text-gray-400 mt-2 pt-2 border-t border-gray-100">
          Self-documenting math &middot; values come straight from the backend.
        </div>
      </div>
    </transition>
  </span>
</template>
