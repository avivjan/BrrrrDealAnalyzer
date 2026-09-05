<script setup lang="ts">
/**
 * A labelled numeric field (percentages, points, counts).
 *
 * Two deliberate details, both fixes for fields that used to fight the user:
 *
 * - **One emit path.** This used to bind `v-model` *and* listen to `@input`,
 *   so every keystroke wrote twice at different points in PrimeVue's lifecycle;
 *   the parent's write-back then re-formatted the input and threw the caret to
 *   the end. Now the value flows in through `:model-value` and out through
 *   `@input` only.
 * - **No fraction mask.** `minFractionDigits` used to become 2 whenever a
 *   sub-1 `step` was passed, so a rate rendered as `6.50` and deleting a single
 *   digit was near-impossible. It is pinned to 0: type as many or as few
 *   decimals as you like.
 */
import InputNumber from "primevue/inputnumber";
import { useId } from "vue";

defineProps<{
  modelValue: number | null;
  /** Omit to render the input bare, when the caller supplies its own label. */
  label?: string;
  suffix?: string;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  required?: boolean;
}>();

const emit = defineEmits(["update:modelValue"]);

const handleKeydown = (e: KeyboardEvent) => {
  // Allow Cmd+A / Ctrl+A to select all
  if ((e.metaKey || e.ctrlKey) && e.key === "a") {
    e.preventDefault();
    const input = e.target as HTMLInputElement;
    if (input && typeof input.select === "function") {
      input.select();
    }
  }
};

const inputId = useId();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <!--
      The id of the `<input>` PrimeVue renders is `inputId` unless the caller
      names one through `data-input-id`. `DaysUntilRefiField` does: it draws the
      visible label itself, and an attribute handed to this component would
      otherwise settle on the wrapper `<div>` rather than reach the field.
    -->
    <label
      v-if="label"
      :for="($attrs['data-input-id'] as string | undefined) ?? inputId"
      data-part="label"
      class="text-sm font-medium text-fg"
      :class="{
        'after:content-[\'*\'] after:ml-0.5 after:text-negative': required,
      }"
    >
      {{ label }}
    </label>
    <InputNumber
      data-part="input"
      :input-id="($attrs['data-input-id'] as string | undefined) ?? inputId"
      :model-value="modelValue"
      :suffix="suffix"
      :min="min"
      :max="max"
      :step="step"
      :placeholder="placeholder"
      :allowEmpty="true"
      :minFractionDigits="0"
      :maxFractionDigits="3"
      inputClass="ui-input tabular"
      class="w-full"
      @keydown="handleKeydown"
      @input="(e: any) => emit('update:modelValue', e.value)"
    />
  </div>
</template>
