<script setup lang="ts">
/**
 * A key-performance tile: eyebrow label, a large numeral in the look's display
 * face, an optional delta, and room for a sparkline underneath.
 *
 * Label, value and delta may arrive as props (the common case — a KPI is data)
 * or as slots of the same names when the caller needs markup in them. The
 * default slot is the chart area; `footer` is a caption line. The tone colours
 * the delta only: a KPI's number is never colour-coded, the delta carries the
 * sign and the colour together so meaning is never colour alone.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Tone = "neutral" | "positive" | "negative" | "warning";

const props = withDefaults(
  defineProps<{
    label?: string;
    value?: string | number;
    delta?: string;
    tone?: Tone;
    /** A primeicons class (`pi pi-home`). Decorative. */
    icon?: string;
  }>(),
  { label: undefined, value: undefined, delta: undefined, tone: "neutral", icon: undefined },
);

defineOptions({ inheritAttrs: false });

const BASE =
  "grid min-h-[7.25rem] grid-rows-[auto_auto_1fr] gap-1 rounded-card border-ui border-line bg-surface p-4 shadow-1 " +
  "transition-[box-shadow,transform,background-color,border-color] duration-fast ease-standard";

const DELTA_TONES: Record<Tone, string> = {
  neutral: "text-fg-muted",
  positive: "text-positive",
  negative: "text-negative",
  warning: "text-warning",
};

const attrs = useAttrs();

/** Everything except `class`, which `rootClass` folds through `cn()`. A function, not a computed — see `UiCard`. */
function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() => cn(BASE, attrs.class as string));
const deltaClass = computed(() => cn("numeric text-xs", DELTA_TONES[props.tone]));
</script>

<template>
  <div data-ui="kpi-card" :class="rootClass" v-bind="passthrough()">
    <div class="flex items-center justify-between gap-2">
      <span data-part="label" class="text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-muted">
        <slot name="label">{{ label }}</slot>
      </span>
      <i v-if="icon" :class="cn(icon, 'text-sm text-fg-muted')" aria-hidden="true" />
    </div>
    <span data-part="value" class="font-display numeric text-2xl leading-tight tracking-display text-fg">
      <slot name="value">{{ value }}</slot>
    </span>
    <div class="flex items-end justify-between gap-2">
      <span v-if="delta || $slots.delta" data-part="delta" :class="deltaClass">
        <slot name="delta">{{ delta }}</slot>
      </span>
      <div v-if="$slots.default" data-part="chart" class="ml-auto h-7 w-full max-w-[9rem] self-end">
        <slot />
      </div>
    </div>
    <div v-if="$slots.footer" data-part="footer" class="text-xs text-fg-muted">
      <slot name="footer" />
    </div>
  </div>
</template>
