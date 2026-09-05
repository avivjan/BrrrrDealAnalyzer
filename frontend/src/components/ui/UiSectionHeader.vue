<script setup lang="ts">
/**
 * A title, an optional line under it, and the controls that belong to the
 * section — laid out as one row so the actions never drift out of line with
 * the heading they act on.
 *
 * `as` sets the heading level and nothing else about where the component may
 * be used: document outline is a property of the page, not of the shape, and a
 * card's header is often an `h3` in a view whose page title is the `h1`. The
 * type scale follows the level rather than a separate `size` prop, because a
 * heading that looks like an `h1` and announces as an `h3` is the failure this
 * is trying to prevent.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Level = "h1" | "h2" | "h3" | "h4";

const props = withDefaults(defineProps<{ as?: Level }>(), { as: "h2" });

defineOptions({ inheritAttrs: false });

const BASE = "flex items-start justify-between gap-3";

const LEVELS: Record<Level, string> = {
  h1: "text-2xl font-bold tracking-tight",
  h2: "text-lg font-semibold",
  h3: "text-base font-semibold",
  h4: "text-sm font-semibold uppercase tracking-wide",
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

const rootClass = computed(() => cn(BASE, attrs.class as string));
const titleClass = computed(() => cn("text-fg", LEVELS[props.as]));
</script>

<template>
  <div data-ui="section-header" :class="rootClass" v-bind="passthrough()">
    <!-- `min-w-0` so a long title truncates instead of shoving the actions off. -->
    <div class="min-w-0">
      <component :is="as" data-part="title" :class="titleClass">
        <slot />
      </component>
      <p v-if="$slots.subtitle" data-part="subtitle" class="mt-0.5 text-sm text-fg-muted">
        <slot name="subtitle" />
      </p>
    </div>
    <div
      v-if="$slots.actions"
      data-part="actions"
      class="flex shrink-0 items-center gap-2"
    >
      <slot name="actions" />
    </div>
  </div>
</template>
