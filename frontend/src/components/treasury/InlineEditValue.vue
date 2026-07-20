<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'

const props = defineProps<{
  modelValue: string | number
  type?: 'text' | 'number'
  currency?: boolean
  decimals?: number
  /** When true, a numeric 0 renders as `emptyLabel` (e.g. an unset target/cap). */
  treatZeroAsUnset?: boolean
  emptyLabel?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  commit: [value: string | number]
}>()

const editing = ref(false)
const draft = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

const isNumber = computed(() => props.type === 'number')

const displayValue = computed(() => {
  if (isNumber.value) {
    const n = Number(props.modelValue)
    if (props.treatZeroAsUnset && (!n || Number.isNaN(n))) {
      return props.emptyLabel ?? 'Unset'
    }
    if (Number.isNaN(n)) return props.emptyLabel ?? '—'
    if (props.currency) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: props.decimals ?? 0,
        maximumFractionDigits: props.decimals ?? 0,
      }).format(n)
    }
    return n.toLocaleString(undefined, {
      minimumFractionDigits: props.decimals ?? 0,
      maximumFractionDigits: props.decimals ?? 4,
    })
  }
  const s = String(props.modelValue ?? '')
  return s.length ? s : props.emptyLabel ?? '—'
})

function startEdit() {
  if (props.disabled) return
  draft.value = String(props.modelValue ?? '')
  editing.value = true
  nextTick(() => {
    inputRef.value?.focus()
    inputRef.value?.select()
  })
}

function commit() {
  if (!editing.value) return
  editing.value = false
  const raw = draft.value.trim()
  if (isNumber.value) {
    const n = Number(raw)
    if (!Number.isNaN(n) && n !== Number(props.modelValue)) {
      emit('commit', n)
    }
    return
  }
  if (raw !== String(props.modelValue ?? '')) {
    emit('commit', raw)
  }
}

function cancel() {
  editing.value = false
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    commit()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    cancel()
  }
}
</script>

<template>
  <span
    v-if="!editing"
    class="inline-edit-value"
    :class="disabled ? 'cursor-default opacity-70' : 'cursor-text hover:bg-white/[0.06]'"
    tabindex="0"
    @click="startEdit"
    @keydown.enter="startEdit"
  >
    <span class="inline-edit-text">{{ displayValue }}</span>
    <i v-if="!disabled" class="pi pi-pencil edit-affordance"></i>
  </span>
  <input
    v-else
    ref="inputRef"
    v-model="draft"
    :type="isNumber ? 'number' : 'text'"
    step="any"
    class="inline-edit-input"
    @blur="commit"
    @keydown="onKeydown"
  />
</template>

<style scoped>
.inline-edit-value {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border-radius: 0.35rem;
  padding: 0.05rem 0.32rem;
  margin: -0.05rem -0.32rem;
  transition: background-color 0.15s ease;
  line-height: 1.2;
}

.inline-edit-text {
  font-variant-numeric: tabular-nums;
}

.edit-affordance {
  font-size: 0.58rem;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.inline-edit-value:hover .edit-affordance,
.inline-edit-value:focus .edit-affordance {
  opacity: 0.55;
}

.inline-edit-input {
  background: transparent;
  border: none;
  border-bottom: 1.5px dashed rgba(129, 140, 248, 0.7);
  outline: none;
  color: inherit;
  font: inherit;
  width: 100%;
  min-width: 3rem;
  padding: 0.05rem 0.1rem;
}
</style>
