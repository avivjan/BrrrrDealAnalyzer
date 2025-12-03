<script setup lang="ts">
import InputNumber from 'primevue/inputnumber';
import Slider from 'primevue/slider';
import { computed } from 'vue';

const props = defineProps<{
  modelValue: number | null;
  label: string;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  required?: boolean;
}>();

const emit = defineEmits(['update:modelValue']);

const value = computed({
  get: () => props.modelValue ?? 0, // Slider needs a number, default to 0 if null
  set: (val) => emit('update:modelValue', val)
});

// For InputNumber, we want to allow nulls if needed, but slider sync implies a value.
// We'll treat null as min or 0.
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex justify-between items-center">
      <label class="text-sm font-medium text-ocean-200" :class="{'after:content-[\'*\'] after:ml-0.5 after:text-red-500': required}">
        {{ label }}
      </label>
      <div class="w-24">
        <InputNumber
          v-model="value"
          :min="min"
          :max="max"
          :suffix="suffix"
          :step="step"
          :minFractionDigits="step && step < 1 ? 2 : 0"
          inputClass="w-full text-right bg-whale-surface border border-whale-surface/50 rounded-lg px-2 py-1 text-sm text-ocean-50 focus:outline-none focus:ring-1 focus:ring-ocean-500"
        />
      </div>
    </div>
    <div class="px-1">
      <Slider
        v-model="value"
        :min="min"
        :max="max"
        :step="step"
        class="w-full h-2 bg-whale-surface rounded-full cursor-pointer relative"
        :pt="{
            range: { class: 'bg-ocean-500 h-full rounded-full absolute top-0 left-0' },
            handle: { class: 'bg-ocean-100 border-2 border-ocean-500 w-5 h-5 rounded-full absolute top-1/2 -mt-2.5 -ml-2.5 shadow-md hover:scale-110 transition-transform focus:outline-none focus:ring-2 focus:ring-ocean-300' }
        }"
      />
    </div>
  </div>
</template>


