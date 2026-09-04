<script setup lang="ts">
/**
 * The panel a modal is drawn on: a rounded surface with a fixed header, a
 * scrolling body and a fixed footer. The overlay is *not* here.
 *
 * That split is the whole point. The overlay `div`, its `@click.self`, the
 * Escape key, the `v-if` that mounts the thing and whatever the app does to
 * the page behind it are behaviour, and behaviour stays in the parent this
 * phase. So this component registers no listener of any kind — nothing on
 * `document`, nothing on `window` — and swapping a hand-rolled panel for it
 * cannot change when a dialog opens or closes. Focus management is the same
 * story: a later phase adds it deliberately, in one place, rather than having
 * it appear the moment a view adopts a primitive.
 *
 * A dialog still has to have a name, which is the one piece of wiring it does
 * do. With no `labelledBy`, the header slot is wrapped in an `<h2>` and the
 * root points at it. With `labelledBy`, the caller owns the heading — and the
 * header slot renders bare, which is what a header holding a title *and* a
 * close button needs: a button inside the `<h2>` would otherwise become part
 * of the dialog's spoken name.
 *
 * The body is the only scroll container, and it is `overscroll-contain`: on
 * iOS a modal that scroll-chains drags the page underneath it.
 */
import { computed, useAttrs, useId, useSlots } from "vue";

import { cn } from "../../design/cn";

type Size = "sm" | "md" | "lg" | "xl" | "full";

const props = withDefaults(
  defineProps<{
    size?: Size;
    /** Id of a heading the caller renders. Suppresses this panel's own `<h2>`. */
    labelledBy?: string;
  }>(),
  { size: "md", labelledBy: undefined },
);

defineOptions({ inheritAttrs: false });

const slots = useSlots();
const attrs = useAttrs();

const headingId = useId();

const BASE = "flex w-full flex-col overflow-hidden rounded-panel bg-surface shadow-3";

/**
 * Every size but `full` is capped below the viewport. It is applied beside the
 * size rather than in `BASE` on purpose: `max-h-none` is not a class
 * tailwind-merge recognises, so a `full` panel could not have overridden it
 * and would have been clamped to 90svh on the very screens it exists to fill.
 */
const CAPPED = "max-h-[90svh]";

/**
 * `full` is the phone treatment: edge to edge and the full visual viewport
 * (`svh`, so the iOS toolbars do not push the footer off-screen), then a
 * normal centred panel from `md` up.
 */
const SIZES: Record<Size, string> = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-3xl",
  xl: "max-w-5xl",
  full: "max-w-none rounded-none h-[100svh] md:h-auto md:max-h-[90svh] md:rounded-panel",
};

/** The panel's own heading is rendered only when the caller has not named one. */
const ownsHeading = computed(() => !props.labelledBy && Boolean(slots.header));
const labelledBy = computed(() => props.labelledBy ?? (slots.header ? headingId : undefined));

/**
 * Everything except `class`, which `rootClass` folds through `cn()` instead.
 * A plain function, not a `computed`: see `UiCard`.
 */
function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() =>
  cn(BASE, props.size !== "full" && CAPPED, SIZES[props.size], attrs.class as string),
);
</script>

<template>
  <div
    data-ui="modal-panel"
    role="dialog"
    aria-modal="true"
    :aria-labelledby="labelledBy"
    :class="rootClass"
    v-bind="passthrough()"
  >
    <header
      v-if="$slots.header"
      data-part="header"
      class="sticky top-0 z-10 shrink-0 border-b border-line bg-surface px-4 py-3 md:px-6"
    >
      <h2 v-if="ownsHeading" :id="headingId" class="text-base font-semibold text-fg">
        <slot name="header" />
      </h2>
      <slot v-else name="header" />
    </header>

    <div
      data-part="body"
      class="custom-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 md:p-6"
    >
      <slot />
    </div>

    <!--
      `pb-safe-b` sits on the region and the padding on an inner box, so the
      home-indicator inset is *added* below the footer's own padding instead of
      replacing it — the inset is 0 on every device without one.
    -->
    <footer
      v-if="$slots.footer"
      data-part="footer"
      class="sticky bottom-0 z-10 shrink-0 border-t border-line bg-surface pb-safe-b"
    >
      <div class="px-4 py-3 md:px-6"><slot name="footer" /></div>
    </footer>
  </div>
</template>
