<template>
  <label class="flex items-center gap-3">
    <div class="relative inline-flex h-6 w-11 items-center">
      <input type="checkbox" class="sr-only" :checked="modelValue" @change="toggle" />
      <div
        class="h-6 w-11 rounded-full bg-ocean-200/50 transition peer-checked:bg-ocean-700"
        :class="modelValue ? 'bg-ocean-700' : 'bg-ocean-200/30'"
      ></div>
      <div
        class="absolute left-1 top-1 h-4 w-4 rounded-full bg-white shadow transition"
        :class="modelValue ? 'translate-x-5' : ''"
      ></div>
    </div>
    <p class="label-text">{{ label }}</p>
  </label>
</template>

<script setup lang="ts">
interface Props {
  modelValue: boolean;
  label: string;
}

const props = defineProps<Props>();
const emit = defineEmits(['update:modelValue']);

const toggle = () => emit('update:modelValue', !props.modelValue);
</script>
