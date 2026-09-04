<script setup lang="ts">
/**
 * The small "Saving… / Saved / Couldn't save" marker beside an autosaving
 * control.
 *
 * Two decisions worth stating:
 *
 * - **Idle renders an empty span, not nothing.** The element stays in the
 *   layout with its height reserved, so the moment a save starts the row does
 *   not jump. `hidden` or a `v-if` in the parent would both reflow the row at
 *   the exact instant the user is typing into it.
 * - **The words are the caller's.** Only the icon and the tone come from here.
 *   Every view keeps its own copy in its own template, which is what the copy
 *   gate reads, and what lets one view say "Saved" and another "All changes
 *   saved" without a prop.
 *
 * `role="status"` makes the span a polite live region, so the label is
 * announced when it changes without interrupting whatever is being read.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Status = "idle" | "saving" | "saved" | "error";

const props = withDefaults(defineProps<{ status?: Status }>(), { status: "idle" });

defineOptions({ inheritAttrs: false });

const BASE = "inline-flex min-h-4 items-center gap-1.5 text-xs leading-none";

const STATES: Record<Status, { icon: string | null; tone: string }> = {
  idle: { icon: null, tone: "text-fg-muted" },
  saving: { icon: "pi pi-spinner pi-spin", tone: "text-fg-muted" },
  saved: { icon: "pi pi-check", tone: "text-positive" },
  error: { icon: "pi pi-exclamation-circle", tone: "text-negative" },
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

const state = computed(() => STATES[props.status]);
const rootClass = computed(() => cn(BASE, state.value.tone, attrs.class as string));
</script>

<template>
  <span
    data-ui="save-status"
    :data-state="status"
    role="status"
    aria-live="polite"
    :class="rootClass"
    v-bind="passthrough()"
  >
    <template v-if="state.icon">
      <i :class="cn(state.icon, 'text-[0.9em]')" aria-hidden="true" />
      <slot />
    </template>
  </span>
</template>
