<script setup lang="ts">
/**
 * A hover/focus tooltip with an accessible fallback.
 *
 * The bubble appears on hover and on focus within. On a touch device there is no
 * hover, so a tap on the trigger toggles it instead (`data-open`) and a tap anywhere
 * else closes it; that keeps the (i) icons of the deal form usable on a phone. The
 * text is still available: the scoped slot hands the trigger an id to put in
 * `aria-describedby`, so a screen reader reads `content` wherever the pointer is.
 * Anything essential belongs in visible copy, not here.
 */
import { computed, onBeforeUnmount, ref, useAttrs, useId } from "vue";

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

const open = ref(false);
const closeOnOutsideTap = (event: Event) => {
  if (!(event.target instanceof Node) || !rootEl.value?.contains(event.target)) open.value = false;
};
const rootEl = ref<HTMLElement | null>(null);
const toggle = () => {
  open.value = !open.value;
  if (open.value) document.addEventListener("pointerdown", closeOnOutsideTap, { capture: true });
  else document.removeEventListener("pointerdown", closeOnOutsideTap, { capture: true });
};
onBeforeUnmount(() => document.removeEventListener("pointerdown", closeOnOutsideTap, { capture: true }));

const bubbleClass = computed(() =>
  cn(
    "pointer-events-none absolute left-1/2 z-40 w-max max-w-[16rem] -translate-x-1/2 rounded-ctl border-ui border-line bg-surface-3 px-2.5 py-1.5 text-xs text-fg shadow-3",
    "opacity-0 transition-opacity duration-fast ease-standard",
    "group-hover:opacity-100 group-focus-within:opacity-100 group-data-[open=true]:opacity-100",
    // G-HOVER pair: on touch the bubble is `display: none` until the trigger is tapped open.
    "touch:opacity-100 touch:hidden touch:group-data-[open=true]:block",
    props.placement === "top" ? "bottom-full mb-2" : "top-full mt-2",
  ),
);
</script>

<template>
  <span ref="rootEl" data-ui="tooltip" :data-open="open" :class="rootClass" v-bind="passthrough()" @click="toggle">
    <slot :described-by="id" />
    <span :id="id" role="tooltip" data-part="bubble" :class="bubbleClass">{{ content }}</span>
  </span>
</template>
