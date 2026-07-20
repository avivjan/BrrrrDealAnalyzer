<script setup lang="ts">
import { ref, watch } from 'vue'
import type { LLCConfiguration } from '../../types/treasury'

const props = defineProps<{
  isOpen: boolean
  llcs: LLCConfiguration[]
}>()

const emit = defineEmits<{
  close: []
  submit: [payload: { property_id?: string; llc_id: string }]
}>()

const propertyId = ref('')
const llcId = ref('')
const submitting = ref(false)
const errorMsg = ref('')

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      propertyId.value = ''
      llcId.value = props.llcs[0]?.llc_id ?? ''
      errorMsg.value = ''
      submitting.value = false
    }
  },
)

function close() {
  if (submitting.value) return
  emit('close')
}

async function submit() {
  if (!llcId.value) {
    errorMsg.value = 'Select an LLC to attach this property to.'
    return
  }
  submitting.value = true
  errorMsg.value = ''
  try {
    const trimmed = propertyId.value.trim()
    emit('submit', { llc_id: llcId.value, ...(trimmed ? { property_id: trimmed } : {}) })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Transition name="modal-fade">
    <div
      v-if="isOpen"
      class="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      @click.self="close"
    >
      <div class="modal-sheet">
        <div class="modal-head">
          <div class="flex items-center gap-2">
            <div class="modal-icon"><i class="pi pi-home"></i></div>
            <h3 class="text-base font-bold text-white">New Property</h3>
          </div>
          <button class="close-btn" @click="close"><i class="pi pi-times"></i></button>
        </div>

        <div class="modal-body">
          <p v-if="errorMsg" class="error-banner">{{ errorMsg }}</p>
          <p v-if="llcs.length === 0" class="hint-banner">
            Create an LLC first — every property must belong to one.
          </p>

          <label class="field">
            <span class="field-label">Attach to LLC</span>
            <select v-model="llcId" class="dark-input" :disabled="llcs.length === 0">
              <option v-for="llc in llcs" :key="llc.llc_id" :value="llc.llc_id">
                {{ llc.llc_name }}
              </option>
            </select>
          </label>

          <label class="field">
            <span class="field-label">Property ID / Address <span class="optional">(optional)</span></span>
            <input
              v-model="propertyId"
              type="text"
              class="dark-input"
              placeholder="e.g. 2897-n-10th-st"
              @keydown.enter="submit"
            />
          </label>
        </div>

        <div class="modal-footer">
          <button class="ghost-btn" @click="close">Cancel</button>
          <button class="primary-btn" :disabled="submitting || llcs.length === 0" @click="submit">
            <i v-if="submitting" class="pi pi-spin pi-spinner"></i>
            {{ submitting ? 'Creating…' : 'Create Property' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-sheet {
  width: 100%;
  max-width: 26rem;
  border-radius: 1.1rem;
  background: #0f1420;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 40px 80px -30px rgba(0, 0, 0, 0.8);
  overflow: hidden;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.15rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.modal-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.6rem;
  background: rgba(16, 185, 129, 0.15);
  color: #6ee7b7;
}

.close-btn {
  color: rgba(255, 255, 255, 0.4);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  transition: color 0.15s ease;
}

.close-btn:hover {
  color: white;
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 1.15rem;
}

.error-banner {
  border-radius: 0.6rem;
  background: rgba(244, 63, 94, 0.12);
  border: 1px solid rgba(244, 63, 94, 0.25);
  color: #fb7185;
  font-size: 0.78rem;
  padding: 0.5rem 0.7rem;
}

.hint-banner {
  border-radius: 0.6rem;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.22);
  color: #fbbf24;
  font-size: 0.78rem;
  padding: 0.5rem 0.7rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.4);
}

.optional {
  text-transform: none;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.25);
}

.dark-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.6rem;
  padding: 0.55rem 0.7rem;
  font-size: 0.88rem;
  color: white;
  outline: none;
  transition: border-color 0.15s ease;
}

.dark-input:focus {
  border-color: rgba(129, 140, 248, 0.6);
}

.dark-input:disabled {
  opacity: 0.5;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  padding: 0.9rem 1.15rem;
  background: rgba(255, 255, 255, 0.02);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.ghost-btn {
  padding: 0.5rem 0.9rem;
  border-radius: 0.6rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  background: transparent;
  border: none;
  cursor: pointer;
}

.ghost-btn:hover {
  background: rgba(255, 255, 255, 0.06);
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  border-radius: 0.6rem;
  font-size: 0.85rem;
  font-weight: 700;
  color: white;
  background: linear-gradient(135deg, #10b981, #0ea5e9);
  border: none;
  cursor: pointer;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
