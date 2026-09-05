<script setup lang="ts">
/**
 * The card shell — a bordered, rounded surface with an optional header and
 * footer.
 *
 * Padding lands on the *regions*, not on the root. A card with a header needs
 * a rule that runs the full width of the shell, and a root that is already
 * padded cannot draw one without a negative margin; giving each region its own
 * padding makes the divider fall out for free and keeps `padding="none"`
 * genuinely edge-to-edge for a card whose body is a table or an image.
 *
 * `as` exists because a card is a shape, not a meaning: the same shell is a
 * `div` in a grid, a `section` on a page and an `li` in a list, and the call
 * site is the only place that knows which.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Tone = "surface" | "muted" | "elevated";
type Padding = "none" | "sm" | "md" | "lg";

const props = withDefaults(
  defineProps<{
    tone?: Tone;
    /** Lift and pointer feedback. Purely visual — the click is the parent's. */
    interactive?: boolean;
    padding?: Padding;
    as?: string;
  }>(),
  { tone: "surface", interactive: false, padding: "md", as: "div" },
);

defineOptions({ inheritAttrs: false });

const BASE =
  "rounded-card border border-line " +
  "transition-[color,background-color,border-color,box-shadow,transform] duration-fast ease-standard";

const TONES: Record<Tone, string> = {
  surface: "bg-surface shadow-1",
  muted: "bg-surface-muted",
  elevated: "bg-surface shadow-2",
};

const INTERACTIVE = "cursor-pointer hover:shadow-2 hover:-translate-y-px active:scale-[0.99]";

const PADDINGS: Record<Padding, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

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

const rootClass = computed(() =>
  cn(BASE, TONES[props.tone], props.interactive && INTERACTIVE, attrs.class as string),
);

const regionClass = computed(() => PADDINGS[props.padding]);
</script>

<template>
  <component :is="as" data-ui="card" :class="rootClass" v-bind="passthrough()">
    <div v-if="$slots.header" data-part="header" :class="cn('border-b border-line', regionClass)">
      <slot name="header" />
    </div>
    <div v-if="$slots.default" data-part="body" :class="regionClass">
      <slot />
    </div>
    <div v-if="$slots.footer" data-part="footer" :class="cn('border-t border-line', regionClass)">
      <slot name="footer" />
    </div>
  </component>
</template>
