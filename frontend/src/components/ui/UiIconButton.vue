<script setup lang="ts">
/**
 * A square, icon-only button.
 *
 * Two things it exists to get right:
 *
 * - **A name.** An icon-only control is anonymous to a screen reader, so
 *   `label` is required and becomes `aria-label`. Vue's own required-prop
 *   warning does not fire for `label=""`, which is the shape this actually
 *   arrives in (an interpolated title that turned out empty), so there is a
 *   dev-only warning of its own — once per instance, not once per render.
 * - **A finger-sized target.** The visual box stays 32/40px so dense toolbars
 *   keep their rhythm, and a transparent `::before` grows the *hit* area to
 *   44px without moving a single neighbour: 32 + 2x6 and 40 + 2x2.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Size = "sm" | "md";
type Variant = "ghost" | "secondary" | "danger";

const props = withDefaults(
  defineProps<{
    /** The accessible name. Required: an icon alone says nothing out loud. */
    label: string;
    size?: Size;
    variant?: Variant;
    type?: "button" | "submit" | "reset";
  }>(),
  { size: "sm", variant: "ghost", type: "button" },
);

defineOptions({ inheritAttrs: false });

const BASE =
  "relative inline-flex shrink-0 select-none items-center justify-center rounded-ctl " +
  "before:absolute before:content-[''] " +
  "transition-[color,background-color,border-color,box-shadow,transform] duration-fast ease-standard " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
  "active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100";

/** Visual box, then the inset that lifts the hit area to 44px. */
const SIZES: Record<Size, string> = {
  sm: "h-8 w-8 text-sm before:-inset-1.5",
  md: "h-10 w-10 text-base before:-inset-0.5",
};

const VARIANTS: Record<Variant, string> = {
  ghost: "text-fg-muted hover:bg-surface-muted hover:text-fg",
  secondary: "border border-line bg-surface text-fg hover:bg-surface-muted",
  danger: "text-negative hover:bg-negative/10",
};

// `?.` is not paranoia: `label` is required at the type level, but a parent
// that simply omits it hands the runtime `undefined`, and that is precisely
// the case the warning is here to catch.
if (import.meta.env.DEV && !props.label?.trim()) {
  console.warn("[UiIconButton] label is required");
}

const attrs = useAttrs();

/** Everything except `class`, which `rootClass` folds through `cn()` instead. */
const passthrough = computed(() => {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
});

const rootClass = computed(() =>
  cn(BASE, SIZES[props.size], VARIANTS[props.variant], attrs.class as string),
);
</script>

<template>
  <button
    data-ui="icon-button"
    :type="type"
    :aria-label="label"
    :class="rootClass"
    v-bind="passthrough"
  >
    <slot />
  </button>
</template>
