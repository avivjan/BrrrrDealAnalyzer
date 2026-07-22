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
// NOTE: the <input> below binds `type` dynamically (`:type="isNumber ? 'number' : 'text'"`).
// Vue's runtime resolves that as `vModelDynamic`, which auto-detects `el.type === 'number'`
// and — exactly like an implicit `.number` modifier — coerces the v-model value to an actual
// JS `number` once the field contains a parseable value. So `draft` can hold either a string
// or a number depending on what's been typed; always coerce with String(...) before treating
// it as text (e.g. `.trim()`), or the commit silently throws and the edit is never saved.
const draft = ref<string | number>('')
const inputRef = ref<HTMLInputElement | null>(null)

const isNumber = computed(() => props.type === 'number')

const numericModel = computed(() => Number(props.modelValue))

const displayValue = computed(() => {
  if (isNumber.value) {
    const n = numericModel.value
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

function startEdit(e: MouseEvent | KeyboardEvent) {
  e.stopPropagation()
  if (props.disabled) return
  draft.value = isNumber.value ? String(numericModel.value) : String(props.modelValue ?? '')
  editing.value = true
  nextTick(() => {
    inputRef.value?.focus()
    inputRef.value?.select()
  })
}

function commit() {
  if (!editing.value) return
  editing.value = false
  // draft.value may already be a `number` (see note above) — normalize to string first.
  const raw = String(draft.value ?? '').trim()
  if (isNumber.value) {
    if (raw === '') return
    const n = Number(raw)
    if (Number.isNaN(n)) return
    const prev = numericModel.value
    if (Number.isNaN(prev) || Math.abs(n - prev) > 1e-9) {
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
  e.stopPropagation()
  if (e.key === 'Enter') {
    e.preventDefault()
    commit()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    cancel()
  }
}

function onInputMouseDown(e: MouseEvent) {
  e.stopPropagation()
}
</script>

<template>
  <span
    v-if="!editing"
    class="inline-edit-value"
    :class="disabled ? 'cursor-default opacity-70' : 'cursor-text hover:bg-white/[0.06]'"
    tabindex="0"
    role="button"
    @click="startEdit"
    @mousedown.stop
    @keydown.enter.prevent="startEdit"
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
    @mousedown="onInputMouseDown"
    @click.stop
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
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(129, 140, 248, 0.45);
  border-radius: 0.35rem;
  outline: none;
  color: inherit;
  font: inherit;
  width: 100%;
  min-width: 3rem;
  padding: 0.15rem 0.35rem;
  z-index: 10;
  position: relative;
}
</style>
