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
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label
      v-if="label"
      class="text-sm font-medium text-gray-700"
      :class="{
        'after:content-[\'*\'] after:ml-0.5 after:text-red-500': required,
      }"
    >
      {{ label }}
    </label>
    <InputNumber
      :model-value="modelValue"
      :suffix="suffix"
      :min="min"
      :max="max"
      :step="step"
      :placeholder="placeholder"
      :allowEmpty="true"
      :minFractionDigits="0"
      :maxFractionDigits="3"
      inputClass="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all hover:bg-gray-50"
      class="w-full"
      @keydown="handleKeydown"
      @input="(e: any) => emit('update:modelValue', e.value)"
    />
  </div>
</template>
