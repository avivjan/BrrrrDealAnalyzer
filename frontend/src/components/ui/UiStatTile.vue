<script setup lang="ts">
/**
 * One number and its caption — the unit the stats bar and the analysis panels
 * are built from.
 *
 * Two details it exists to enforce:
 *
 * - **A red number is not a message.** Every non-neutral tone carries an arrow
 *   (or a warning triangle) *and* a visually hidden word, so "this is negative"
 *   survives a colour-blind reader, a greyscale print and a screen reader. The
 *   icon is `aria-hidden`; the word is the thing that is actually announced.
 * - **Digits must not dance.** The value is `tabular`, so a figure ticking from
 *   $1,199 to $1,240 changes its digits without changing its width.
 *
 * The label may come from the `#label` slot or the `label` prop; the slot wins.
 * The prop is there for the many call sites whose caption is a plain string,
 * and both are the caller's copy either way.
 */
import { computed, useAttrs, useSlots } from "vue";

import { cn } from "../../design/cn";

type Tone = "neutral" | "positive" | "negative" | "warning";
type Size = "sm" | "md";

const props = withDefaults(
  defineProps<{
    tone?: Tone;
    size?: Size;
    /** Fallback caption; the `#label` slot takes precedence. */
    label?: string;
  }>(),
  { tone: "neutral", size: "sm", label: undefined },
);

defineOptions({ inheritAttrs: false });

// No transition utilities: the tile is a read-only readout with no hover,
// focus or active state, and easing a value or its tone into place would
// delay the number rather than explain it.
const BASE = "rounded-card bg-surface-muted p-3";

/**
 * `word` is announced, `icon` is not: together they are the two non-colour
 * channels the tone travels on.
 */
const TONES: Record<Tone, { icon: string | null; word: string | null; text: string }> = {
  neutral: { icon: null, word: null, text: "text-fg" },
  positive: { icon: "pi pi-arrow-up", word: "positive", text: "text-positive" },
  negative: { icon: "pi pi-arrow-down", word: "negative", text: "text-negative" },
  warning: { icon: "pi pi-exclamation-triangle", word: "warning", text: "text-warning" },
};

const VALUE_SIZES: Record<Size, string> = {
  sm: "text-base",
  md: "text-xl",
};

const slots = useSlots();
const attrs = useAttrs();

/**
 * Everything except `class`, which `rootClass` folds through `cn()` instead.
 *
 * A plain function rather than a `computed`, and it matters: the object
 * `useAttrs()` hands back tracks a read of a *key*, so spreading it while it
 * holds no keys registers no dependency at all. A computed would cache that
 * first empty result for the life of the component and quietly swallow every
 * attribute the parent adds later. Recomputing per render costs one object.
 */
function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const tone = computed(() => TONES[props.tone]);
const hasLabel = computed(() => Boolean(slots.label || props.label));
const rootClass = computed(() => cn(BASE, attrs.class as string));
const valueClass = computed(() =>
  cn("tabular font-semibold leading-tight", VALUE_SIZES[props.size], tone.value.text),
);
</script>

<template>
  <div data-ui="stat-tile" :class="rootClass" v-bind="passthrough()">
    <span v-if="hasLabel" data-part="label" class="block text-xs font-medium text-fg-muted">
      <slot name="label">{{ label }}</slot>
    </span>
    <span class="mt-1 flex items-baseline gap-1.5">
      <i v-if="tone.icon" :class="cn(tone.icon, 'text-[0.7em]', tone.text)" aria-hidden="true" />
      <span v-if="tone.word" class="sr-only">{{ tone.word }}</span>
      <span data-part="value" :class="valueClass"><slot /></span>
    </span>
    <span v-if="$slots.hint" data-part="hint" class="mt-1 block text-xs text-fg-muted">
      <slot name="hint" />
    </span>
  </div>
</template>
