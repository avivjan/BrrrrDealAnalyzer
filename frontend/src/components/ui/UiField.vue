<script setup lang="ts">
/**
 * The wrapper around one form control: its label, its helper text and its
 * error, wired together by id.
 *
 * The control itself is *never* rendered here — the default slot is scoped and
 * the parent renders its own `<input>`, `<InputNumber>` or `<MoneyInput>`
 * inside it, binding the three values it is handed. That is deliberate: every
 * `v-model`, every `@blur` and every formatting rule stays in the template that
 * owns it, so wrapping an existing field changes markup and nothing else. It
 * also means this component never has to know which of a dozen control kinds
 * it is holding.
 *
 * What it does own is the plumbing a hand-written field keeps getting wrong:
 * one id shared by the label's `for` and the control, and an
 * `aria-describedby` that lists the messages actually on screen, helper first
 * and error second — the order they are read in. An error the user cannot see
 * is never referenced, and a field with no messages has no `aria-describedby`
 * at all rather than one pointing at an empty node.
 *
 * The required marker travels on two channels: an asterisk for the eye (hidden
 * from assistive tech, because "asterisk" is not a word) and a visually hidden
 * "required" for the ear.
 */
import { computed, useAttrs, useId, useSlots } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(
  defineProps<{
    /** The control's id. Generated when omitted; pass one to match a label elsewhere. */
    id?: string;
    required?: boolean;
    invalid?: boolean;
    /** Label beside the control rather than above it. */
    inline?: boolean;
  }>(),
  { id: undefined, required: false, invalid: false, inline: false },
);

defineOptions({ inheritAttrs: false });

const slots = useSlots();
const attrs = useAttrs();

const fallbackId = useId();

const id = computed(() => props.id ?? fallbackId);
const helperId = computed(() => `${id.value}-helper`);
const errorId = computed(() => `${id.value}-error`);

/**
 * Only the messages that are really rendered, in reading order. `undefined`
 * rather than `""` so the parent's `:aria-describedby` binding drops the
 * attribute entirely.
 */
const describedBy = computed(() => {
  const ids = [slots.helper && helperId.value, slots.error && errorId.value].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
});

/** What the parent binds onto its own control. */
const controlProps = computed(() => ({
  id: id.value,
  describedBy: describedBy.value,
  invalid: props.invalid,
}));

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
  cn(props.inline && "flex flex-wrap items-center gap-x-3", attrs.class as string),
);

const labelClass = computed(() =>
  cn("text-sm font-medium text-fg", props.inline ? "shrink-0" : "mb-1.5 block"),
);

/** Inline pushes the control to the far edge; messages still get their own row. */
const controlClass = computed(() => (props.inline ? "ml-auto min-w-0" : ""));
const messageClass = computed(() => (props.inline ? "mt-1 basis-full text-xs" : "mt-1 text-xs"));
</script>

<template>
  <div data-ui="field" :class="rootClass" v-bind="passthrough()">
    <label v-if="$slots.label" :for="id" data-part="label" :class="labelClass">
      <slot name="label" />
      <template v-if="required">
        <span data-part="required" aria-hidden="true" class="text-negative">*</span>
        <span class="sr-only">required</span>
      </template>
    </label>

    <div data-part="control" :class="controlClass">
      <slot v-bind="controlProps" />
    </div>

    <p v-if="$slots.helper" :id="helperId" :class="cn(messageClass, 'text-fg-muted')">
      <slot name="helper" />
    </p>
    <p v-if="$slots.error" :id="errorId" role="alert" :class="cn(messageClass, 'text-negative')">
      <slot name="error" />
    </p>
  </div>
</template>
