<script setup lang="ts">
/**
 * A hover/focus tooltip with an accessible fallback.
 *
 * The bubble appears on hover and on focus within. On a touch device there is no
 * hover, so a tap on the trigger toggles it instead (`data-isOpenedByTap`) and a tap anywhere
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

// A *named* group: the deal form's root is a plain `group` too, and an unnamed
// `group-hover:` would open every tooltip inside it while the pointer is anywhere over the form.
const rootClass = computed(() => cn("group/tooltip relative inline-flex", attrs.class as string));

const isOpenedByTap = ref(false);
const closeOnOutsideTap = (event: Event) => {
  if (!(event.target instanceof Node) || !rootElement.value?.contains(event.target)) isOpenedByTap.value = false;
};
const rootElement = ref<HTMLElement | null>(null);
const toggleOpenedByTap = () => {
  isOpenedByTap.value = !isOpenedByTap.value;
  if (isOpenedByTap.value) document.addEventListener("pointerdown", closeOnOutsideTap, { capture: true });
  else document.removeEventListener("pointerdown", closeOnOutsideTap, { capture: true });
};
onBeforeUnmount(() => document.removeEventListener("pointerdown", closeOnOutsideTap, { capture: true }));

const bubbleClass = computed(() =>
  cn(
    "pointer-events-none absolute left-1/2 z-40 w-max max-w-[16rem] -translate-x-1/2 rounded-ctl border-ui border-line bg-surface-3 px-2.5 py-1.5 text-xs text-fg shadow-3",
    "opacity-0 transition-opacity duration-fast ease-standard",
    "group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100 group-data-[open=true]/tooltip:opacity-100",
    // G-HOVER pair: on touch the bubble is `display: none` until the trigger is tapped isOpenedByTap.
    "touch:opacity-100 touch:hidden touch:group-data-[open=true]/tooltip:block",
    props.placement === "top" ? "bottom-full mb-2" : "top-full mt-2",
  ),
);
</script>

<template>
  <span ref="rootElement" data-ui="tooltip" :data-open="isOpenedByTap" :class="rootClass" v-bind="passthrough()" @click="toggleOpenedByTap">
    <slot :described-by="id" />
    <span :id="id" role="tooltip" data-part="bubble" :class="bubbleClass">{{ content }}</span>
  </span>
</template>
