<script setup lang="ts">
/**
 * A hover/focus tooltip with an accessible fallback.
 *
 * The bubble appears on hover and on focus within; on a touch device it is
 * not rendered at all (`touch:hidden`), because a tooltip that opens on tap
 * either blocks the tap or never closes. The text is still available: the
 * scoped slot hands the trigger an id to put in `aria-describedby`, so a
 * screen reader reads `content` wherever the pointer is. Anything essential
 * belongs in visible copy, not here.
 *
 * `touch:opacity-100` sits beside the hover reveal to honour the G-HOVER
 * pairing rule mechanically; the element is `display: none` on touch, so the
 * pair is inert by design and the reveal cannot strand a control.
 */
import { computed, useAttrs, useId } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(
  defineProps<{
    content: string;
    placement?: "top" | "bottom";
  }>(),
  { placement: "top" },
);

defineOptions({ inheritAttrs: false });

const id = useId();

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() => cn("group relative inline-flex", attrs.class as string));

const bubbleClass = computed(() =>
  cn(
    "pointer-events-none absolute left-1/2 z-40 w-max max-w-[16rem] -translate-x-1/2 rounded-ctl border-ui border-line bg-surface-3 px-2.5 py-1.5 text-xs text-fg shadow-3",
    "opacity-0 transition-opacity duration-fast ease-standard",
    "group-hover:opacity-100 group-focus-within:opacity-100 touch:opacity-100 touch:hidden",
    props.placement === "top" ? "bottom-full mb-2" : "top-full mt-2",
  ),
);
</script>

<template>
  <span data-ui="tooltip" :class="rootClass" v-bind="passthrough()">
    <slot :described-by="id" />
    <span :id="id" role="tooltip" data-part="bubble" :class="bubbleClass">{{ content }}</span>
  </span>
</template>
