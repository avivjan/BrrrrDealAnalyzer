<script setup lang="ts">
import InputNumber from 'primevue/inputnumber';
import { computed } from 'vue';

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

const emit = defineEmits(['update:modelValue']);

const value = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
});
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label class="text-sm font-medium text-ocean-200" :class="{'after:content-[\'*\'] after:ml-0.5 after:text-red-500': required}">
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
      inputClass="w-full bg-whale-surface border border-whale-surface/50 rounded-lg px-3 py-2 text-ocean-50 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-ocean-500 transition-all hover:bg-whale-surface/80"
      class="w-full"
    />
  </div>
</template>


