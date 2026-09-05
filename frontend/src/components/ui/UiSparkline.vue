<script setup lang="ts">
/**
 * A tiny inline trend line. Decorative by contract: the number it illustrates
 * sits beside it in text, so the SVG is `aria-hidden` and carries no title.
 *
 * Drawn to its own scale — the path spans the full width and the min/max of
 * `points` fill the height — with an emphasised endpoint. Colour is
 * `currentColor`, so a `text-accent` on the caller's side recolours it, and
 * the fill is the same colour at low alpha.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Tone = "accent" | "primary" | "positive" | "negative" | "warning" | "muted";

const props = withDefaults(
  defineProps<{
    points: number[];
    tone?: Tone;
    filled?: boolean;
  }>(),
  { tone: "accent", filled: true },
);

defineOptions({ inheritAttrs: false });

const W = 100;
const H = 28;
const PAD = 2;

const TONES: Record<Tone, string> = {
  accent: "text-accent",
  primary: "text-primary",
  positive: "text-positive",
  negative: "text-negative",
  warning: "text-warning",
  muted: "text-fg-muted",
};

/** `[x, y]` per point in viewBox units; a single point becomes a flat line. */
const coords = computed<[number, number][]>(() => {
  const pts = props.points.length === 1 ? [props.points[0]!, props.points[0]!] : props.points;
  if (pts.length === 0) return [];
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const span = max - min || 1;
  const stepX = W / (pts.length - 1);
  return pts.map((v, i) => [i * stepX, H - PAD - ((v - min) / span) * (H - PAD * 2)]);
});

const linePath = computed(() =>
  coords.value.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" "),
);

const areaPath = computed(() =>
  coords.value.length === 0 ? "" : `${linePath.value} L${W},${H} L0,${H} Z`,
);

const end = computed(() => (coords.value.length > 0 ? coords.value[coords.value.length - 1]! : null));

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() => cn("block h-full w-full", TONES[props.tone], attrs.class as string));
</script>

<template>
  <svg
    data-ui="sparkline"
    :viewBox="`0 0 ${W} ${H}`"
    preserveAspectRatio="none"
    aria-hidden="true"
    focusable="false"
    :class="rootClass"
    v-bind="passthrough()"
  >
    <path v-if="filled && areaPath" data-part="area" :d="areaPath" fill="currentColor" opacity="0.14" />
    <path
      v-if="linePath"
      data-part="line"
      :d="linePath"
      fill="none"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linejoin="round"
      stroke-linecap="round"
      vector-effect="non-scaling-stroke"
    />
    <circle v-if="end" data-part="end" :cx="end[0]" :cy="end[1]" r="2.25" fill="currentColor" />
  </svg>
</template>
