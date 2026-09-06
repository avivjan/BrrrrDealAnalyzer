<script setup lang="ts">
/**
 * A circular progress indicator. `value` is 0–1; `label` is required because
 * the ring is an image to assistive tech (`role="img"`) and an unlabelled image
 * says nothing. The percentage is also rendered as text in the centre unless
 * the default slot replaces it, so the meaning is never the arc alone.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Tone = "primary" | "accent" | "positive" | "negative" | "warning";

const props = withDefaults(
  defineProps<{
    /** 0..1; clamped. */
    value: number;
    /** The accessible name, e.g. "3 of 5 substages done". */
    label: string;
    /** Outer diameter in CSS px. */
    size?: number;
    /** Stroke width in CSS px. */
    thickness?: number;
    tone?: Tone;
  }>(),
  { size: 40, thickness: 4, tone: "primary" },
);

defineOptions({ inheritAttrs: false });

const TONES: Record<Tone, string> = {
  primary: "text-primary",
  accent: "text-accent",
  positive: "text-positive",
  negative: "text-negative",
  warning: "text-warning",
};

const clamped = computed(() => Math.min(1, Math.max(0, Number.isFinite(props.value) ? props.value : 0)));
const radius = computed(() => (props.size - props.thickness) / 2);
const circumference = computed(() => 2 * Math.PI * radius.value);
const dashOffset = computed(() => circumference.value * (1 - clamped.value));
const percent = computed(() => `${Math.round(clamped.value * 100)}%`);

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() =>
  cn("relative inline-grid place-items-center", TONES[props.tone], attrs.class as string),
);
</script>

<template>
  <span
    data-ui="progress-ring"
    role="img"
    :aria-label="label"
    :class="rootClass"
    :style="{ width: `${size}px`, height: `${size}px` }"
    v-bind="passthrough()"
  >
    <svg :viewBox="`0 0 ${size} ${size}`" :width="size" :height="size" class="absolute inset-0 -rotate-90" aria-hidden="true" focusable="false">
      <circle
        data-part="track"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        stroke="currentColor"
        :stroke-width="thickness"
        opacity="0.18"
      />
      <circle
        data-part="arc"
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        stroke="currentColor"
        :stroke-width="thickness"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
        class="transition-[stroke-dashoffset] duration-slow ease-standard"
      />
    </svg>
    <span data-part="text" class="numeric relative text-[0.6rem] font-semibold leading-none text-fg" aria-hidden="true">
      <slot>{{ percent }}</slot>
    </span>
  </span>
</template>
