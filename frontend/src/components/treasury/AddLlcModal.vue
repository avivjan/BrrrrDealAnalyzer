<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  close: []
  submit: [payload: { llc_name: string; checking_redline_buffer: number }]
}>()

const name = ref('')
const buffer = ref(1000)
const submitting = ref(false)
const errorMsg = ref('')

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      name.value = ''
      buffer.value = 1000
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
  if (!name.value.trim()) {
    errorMsg.value = 'LLC name is required.'
    return
  }
  submitting.value = true
  errorMsg.value = ''
  try {
    emit('submit', { llc_name: name.value.trim(), checking_redline_buffer: Number(buffer.value) || 0 })
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
            <div class="modal-icon"><i class="pi pi-building"></i></div>
            <h3 class="text-base font-bold text-white">New LLC</h3>
          </div>
          <button class="close-btn" @click="close"><i class="pi pi-times"></i></button>
        </div>

        <div class="modal-body">
          <p v-if="errorMsg" class="error-banner">{{ errorMsg }}</p>

          <label class="field">
            <span class="field-label">LLC Name</span>
            <input
              v-model="name"
              type="text"
              class="dark-input"
              placeholder="e.g. Big Whales AY LLC"
              @keydown.enter="submit"
            />
          </label>

          <label class="field">
            <span class="field-label">Checking Redline Buffer ($)</span>
            <input v-model.number="buffer" type="number" step="0.01" class="dark-input" @keydown.enter="submit" />
          </label>
        </div>

        <div class="modal-footer">
          <button class="ghost-btn" @click="close">Cancel</button>
          <button class="primary-btn" :disabled="submitting" @click="submit">
            <i v-if="submitting" class="pi pi-spin pi-spinner"></i>
            {{ submitting ? 'Creating…' : 'Create LLC' }}
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
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
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
  background: linear-gradient(135deg, #6366f1, #7c3aed);
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
