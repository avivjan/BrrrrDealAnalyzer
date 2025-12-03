<template>
  <label class="space-y-2">
    <div class="flex items-center justify-between">
      <p class="label-text">{{ label }}<span v-if="required" class="text-ocean-800 ml-1">*</span></p>
      <slot name="trailing" />
    </div>
    <div class="relative">
      <span v-if="prefix" class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">{{ prefix }}</span>
      <InputNumber
        v-model="internalValue"
        :input-id="label"
        :class="['input-base', prefix ? 'pl-8' : '']"
        :min="0"
        :step="step"
        mode="decimal"
        :use-grouping="false"
        @blur="$emit('blur')"
      />
    </div>
  </label>
</template>

<script setup lang="ts">
import InputNumber from 'primevue/inputnumber';
import { computed } from 'vue';

interface Props {
  modelValue?: number;
  label: string;
  prefix?: string;
  step?: number;
  required?: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits(['update:modelValue', 'blur']);

const internalValue = computed({
  get: () => props.modelValue ?? 0,
  set: (val: number | null) => emit('update:modelValue', val ?? 0)
});

const step = computed(() => props.step ?? 0.01);
</script>
