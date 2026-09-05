<script setup lang="ts">
/**
 * The inset track a row of tabs sits in. A container and nothing more.
 *
 * The tabs themselves stay in the view's own `v-for`, as `UiButton
 * variant="tab" :active`, because which tab is selected — and what selecting
 * one does — is behaviour this phase does not move. That also keeps the labels
 * in the template that owns them.
 *
 * `overflow-x-auto` rather than `flex-wrap`: six deal filters on a phone should
 * scroll as one row, not restack into two and change the height of everything
 * below them.
 *
 * `ariaLabel` is optional because a tablist that already sits under a visible
 * heading does not need a second name; pass one when it does not.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

withDefaults(defineProps<{ ariaLabel?: string }>(), { ariaLabel: undefined });

defineOptions({ inheritAttrs: false });

const BASE = "inline-flex items-center gap-1 overflow-x-auto rounded-ctl bg-surface-muted p-1";

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
</script>

<template>
  <div
    data-ui="tabs"
    role="tablist"
    :aria-label="ariaLabel"
    :class="rootClass"
    v-bind="passthrough()"
  >
    <slot />
  </div>
</template>
