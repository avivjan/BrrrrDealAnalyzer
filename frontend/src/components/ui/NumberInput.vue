<script setup lang="ts">
import InputNumber from "primevue/inputnumber";
import { computed } from "vue";

const props = defineProps<{
  modelValue: number | null;
  label: string;
  suffix?: string;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  required?: boolean;
}>();

const emit = defineEmits(["update:modelValue"]);

const value = computed({
  get: () => props.modelValue,
  set: (val) => emit("update:modelValue", val),
});

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
      class="text-sm font-medium text-gray-700"
      :class="{
        'after:content-[\'*\'] after:ml-0.5 after:text-red-500': required,
      }"
    >
      {{ label }}
    </label>
    <InputNumber
      v-model="value"
      :suffix="suffix"
      :min="min"
      :max="max"
      :step="step"
      :placeholder="placeholder"
      :allowEmpty="true"
      :minFractionDigits="step && step < 1 ? 2 : 0"
      :maxFractionDigits="2"
      inputClass="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all hover:bg-gray-50"
      class="w-full"
      @keydown="handleKeydown"
    />
  </div>
</template>


