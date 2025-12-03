<template>
  <label class="space-y-2">
    <p class="label-text">{{ label }}<span v-if="required" class="text-ocean-800 ml-1">*</span></p>
    <input
      :value="modelValue"
      class="input-base"
      :placeholder="placeholder"
      @input="onInput"
      :type="type"
    />
  </label>
</template>

<script setup lang="ts">
interface Props {
  modelValue?: string | number | null;
  label: string;
  placeholder?: string;
  required?: boolean;
  type?: string;
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text'
});
const emit = defineEmits(['update:modelValue']);

const onInput = (event: Event) => {
  const target = event.target as HTMLInputElement;
  emit('update:modelValue', target.value);
};
</script>
