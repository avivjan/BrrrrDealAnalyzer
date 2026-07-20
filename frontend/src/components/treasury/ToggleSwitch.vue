<script setup lang="ts">
const props = defineProps<{
  modelValue: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

function toggle() {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
}
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="modelValue"
    class="toggle-switch"
    :class="modelValue ? 'toggle-on' : 'toggle-off'"
    :disabled="disabled"
    @click="toggle"
  >
    <span class="toggle-knob"></span>
  </button>
</template>

<style scoped>
.toggle-switch {
  position: relative;
  width: 2.5rem;
  height: 1.4rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.toggle-off {
  background: rgba(255, 255, 255, 0.08);
}

.toggle-on {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border-color: transparent;
  box-shadow: 0 0 12px -2px rgba(129, 140, 248, 0.6);
}

.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 50%;
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.toggle-on .toggle-knob {
  transform: translateX(1.1rem);
}

.toggle-switch:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
