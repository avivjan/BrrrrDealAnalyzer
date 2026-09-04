<script setup lang="ts">
/**
 * The grey shape that stands in for content still loading.
 *
 * It is `aria-hidden` and carries no text: a screen reader gains nothing from
 * "loading, loading, loading", and the announcement belongs on the region that
 * knows what it is waiting for (`aria-busy`) rather than on the scaffolding.
 *
 * The pulse is a plain `animate-pulse`. The global
 * `@media (prefers-reduced-motion: reduce)` rule in `main.css` already cuts
 * every animation to 0.01 ms, so a reader who has asked for stillness gets a
 * flat grey block with no extra code here.
 *
 * Size comes from the caller's own classes on the root — a skeleton is only
 * useful when it is the size of the thing it replaces, and that is knowledge
 * the call site has. `lines` is the one case worth encoding: a paragraph, whose
 * last bar is short so the block reads as prose rather than as a table.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Rounded = "ctl" | "card" | "full";

const props = withDefaults(defineProps<{ lines?: number; rounded?: Rounded }>(), {
  lines: 1,
  rounded: "ctl",
});

defineOptions({ inheritAttrs: false });

const RADII: Record<Rounded, string> = {
  ctl: "rounded-ctl",
  card: "rounded-card",
  full: "rounded-full",
};

const attrs = useAttrs();

/**
 * Everything except `class`, which `rootClass` folds through `cn()` instead.
 * A plain function, not a `computed`: see `UiCard`.
 */
function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const isParagraph = computed(() => props.lines > 1);

const rootClass = computed(() =>
  cn("animate-pulse", isParagraph.value && "flex flex-col gap-2", attrs.class as string),
);

/**
 * One bar fills whatever box the caller sized; `min-h-4` keeps it visible when
 * no height was given at all. Several bars are text lines, and the last one is
 * short.
 */
function barClass(index: number): string {
  return cn(
    "block bg-surface-muted",
    RADII[props.rounded],
    isParagraph.value ? "h-4" : "h-full min-h-4",
    isParagraph.value && index === props.lines ? "w-2/3" : "w-full",
  );
}
</script>

<template>
  <div data-ui="skeleton" aria-hidden="true" :class="rootClass" v-bind="passthrough()">
    <span v-for="line in lines" :key="line" data-part="bar" :class="barClass(line)" />
  </div>
</template>
