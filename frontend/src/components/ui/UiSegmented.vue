<script setup lang="ts">
/**
 * A segmented control: one choice among a few, shown as a row of connected
 * buttons. Radio semantics (`role="radiogroup"` / `role="radio"`): the
 * checked segment is the one tab stop, and the arrow keys move the choice.
 *
 * `v-model` is the whole contract. The control renders the options it is
 * given and emits the value the user lands on; what that value means is the
 * caller's business.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

export interface SegmentedOption<T extends string = string> {
  value: T;
  label: string;
  /** A primeicons class. Decorative. */
  icon?: string;
}

const props = withDefaults(
  defineProps<{
    options: SegmentedOption[];
    modelValue: string;
    /** The group's accessible name. */
    ariaLabel: string;
    size?: "sm" | "md";
    block?: boolean;
  }>(),
  { size: "md", block: false },
);

const emit = defineEmits<{ "update:modelValue": [value: string] }>();

defineOptions({ inheritAttrs: false });

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const index = computed(() => props.options.findIndex((option) => option.value === props.modelValue));

function move(delta: number) {
  if (props.options.length === 0) return;
  const from = index.value < 0 ? 0 : index.value;
  const next = (from + delta + props.options.length) % props.options.length;
  emit("update:modelValue", props.options[next]!.value);
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case "ArrowRight":
    case "ArrowDown":
      event.preventDefault();
      move(1);
      break;
    case "ArrowLeft":
    case "ArrowUp":
      event.preventDefault();
      move(-1);
      break;
    case "Home":
      event.preventDefault();
      emit("update:modelValue", props.options[0]!.value);
      break;
    case "End":
      event.preventDefault();
      emit("update:modelValue", props.options[props.options.length - 1]!.value);
      break;
    default:
  }
}

const rootClass = computed(() =>
  cn(
    "inline-flex items-stretch gap-1 rounded-ctl border-ui border-line bg-surface-2 p-1",
    props.block && "flex w-full",
    attrs.class as string,
  ),
);

const SIZES = { sm: "min-h-8 px-2.5 text-xs", md: "min-h-9 touch:min-h-11 px-3 text-sm" } as const;
</script>

<template>
  <div
    data-ui="segmented"
    role="radiogroup"
    :aria-label="ariaLabel"
    :class="rootClass"
    v-bind="passthrough()"
    @keydown="onKeydown"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="option.value === modelValue"
      :tabindex="option.value === modelValue || (index < 0 && option === options[0]) ? 0 : -1"
      :data-value="option.value"
      :class="
        cn(
          'inline-flex flex-1 items-center justify-center gap-1.5 rounded-[calc(var(--radius-sm)-2px)] font-medium',
          'transition-[color,background-color,box-shadow] duration-fast ease-standard',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          SIZES[size],
          option.value === modelValue ? 'bg-surface text-fg shadow-1' : 'text-fg-muted hover:text-fg',
        )
      "
      @click="emit('update:modelValue', option.value)"
    >
      <i v-if="option.icon" :class="cn(option.icon, 'text-xs')" aria-hidden="true" />
      <span>{{ option.label }}</span>
    </button>
  </div>
</template>
