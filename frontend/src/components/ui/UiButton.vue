<script setup lang="ts">
/**
 * The app's button.
 *
 * It is deliberately thin: the parent keeps the click, the `disabled`
 * decision and every piece of copy, so swapping a `<button>` for a `UiButton`
 * moves styling and nothing else. Two consequences worth naming:
 *
 * - **`loading` does not disable.** Several call sites want a spinner while a
 *   background refresh runs and still want the button pressable; the ones that
 *   do not simply keep passing `:disabled`. Guessing here would silently
 *   change behaviour.
 * - **`$attrs` reach the button, not a wrapper.** `inheritAttrs` is off and
 *   the attributes are re-bound by hand, so `class` can go through `cn()`
 *   (where tailwind-merge drops what the caller means to override) while
 *   `data-testid`, `aria-*` and native listeners land on the real element.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "brrrr" | "flip" | "tab";
type Size = "sm" | "md" | "lg";

const props = withDefaults(
  defineProps<{
    variant?: Variant;
    size?: Size;
    /** Shows a spinner and sets `aria-busy`; never sets `disabled`. */
    loading?: boolean;
    block?: boolean;
    type?: "button" | "submit" | "reset";
    /** The selected tab, for `variant="tab"`. Ignored by every other variant. */
    active?: boolean;
  }>(),
  { variant: "primary", size: "md", loading: false, block: false, type: "button", active: false },
);

defineOptions({ inheritAttrs: false });

const BASE =
  "relative inline-flex select-none items-center justify-center gap-2 rounded-ctl font-medium " +
  "transition-[color,background-color,border-color,box-shadow,transform] duration-fast ease-standard " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
  "active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100";

/**
 * `text-primary-fg` is the ink for a filled accent — white in the light theme,
 * slate-900 in the dark one — so `danger` and `flip` reuse it rather than
 * hard-coding a literal that would invert wrongly.
 */
const VARIANTS: Record<Variant, string> = {
  primary: "bg-primary text-primary-fg hover:bg-primary-hover",
  secondary: "border border-line bg-surface text-fg hover:bg-surface-muted",
  ghost: "text-fg hover:bg-surface-muted",
  danger: "bg-negative text-primary-fg hover:bg-negative/90",
  // The BRRRR strategy's accent is the app's accent; it exists as its own name
  // so a call site can say what it means rather than which colour it wants.
  brrrr: "bg-primary text-primary-fg hover:bg-primary-hover",
  flip: "bg-warning text-primary-fg hover:bg-warning/90",
  tab: "text-fg-muted hover:bg-surface-muted",
};

const TAB_ACTIVE = "bg-surface text-fg shadow-1";

const SIZES: Record<Size, string> = {
  sm: "min-h-6 px-2.5 text-xs",
  md: "min-h-11 px-4 text-sm",
  lg: "min-h-12 px-5 text-base",
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
  cn(
    BASE,
    VARIANTS[props.variant],
    props.variant === "tab" && props.active && TAB_ACTIVE,
    SIZES[props.size],
    props.block && "w-full",
    attrs.class as string,
  ),
);

const isTab = computed(() => props.variant === "tab");
</script>

<template>
  <button
    data-ui="button"
    :type="type"
    :role="isTab ? 'tab' : undefined"
    :aria-selected="isTab ? active : undefined"
    :aria-busy="loading || undefined"
    :class="rootClass"
    v-bind="passthrough()"
  >
    <i v-if="loading" class="pi pi-spinner pi-spin text-[0.85em]" aria-hidden="true" />
    <slot />
  </button>
</template>
