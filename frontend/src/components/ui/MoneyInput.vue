<script setup lang="ts">
import InputNumber from 'primevue/inputnumber';
import { computed } from 'vue';

const props = defineProps<{
  modelValue: number | null;
  label: string;
  placeholder?: string;
  min?: number;
  max?: number;
  required?: boolean;
  disabled?: boolean;
  inThousands?: boolean;
}>();

const emit = defineEmits(['update:modelValue']);

const value = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
});

const displayLabel = computed(() => {
  return props.inThousands ? `${props.label} ($000s)` : props.label;
});
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label class="text-sm font-medium text-ocean-200" :class="{'after:content-[\'*\'] after:ml-0.5 after:text-red-500': required}">
      {{ displayLabel }}
    </label>
    <InputNumber
      v-model="value"
      mode="currency"
      currency="USD"
      locale="en-US"
      :min="min"
      :max="max"
      :placeholder="placeholder"
      :disabled="disabled"
      :allowEmpty="true"
      :minFractionDigits="0"
      :maxFractionDigits="0"
      inputClass="w-full bg-whale-surface border border-whale-surface/50 rounded-lg px-3 py-2 text-ocean-50 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-ocean-500 transition-all hover:bg-whale-surface/80"
      class="w-full"
    />
  </div>
</template>


