<script setup lang="ts">
import { ref, watch } from 'vue'
import type { LiquiditySettings } from '../../types/liquidity'

const props = defineProps<{
  open: boolean
  settings: LiquiditySettings
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: { opening_balance_k: number; opening_balance_date: string; reserve_k: number }): void
}>()

const balanceK = ref('')
const balanceDate = ref('')
const reserveK = ref('')

watch(() => props.open, (open) => {
  if (!open) return
  balanceK.value = props.settings.opening_balance_k.toString()
  balanceDate.value = props.settings.opening_balance_date
  reserveK.value = props.settings.reserve_k.toString()
})

function onSave() {
  const b = parseFloat(balanceK.value)
  const r = parseFloat(reserveK.value)
  if (isNaN(b) || !balanceDate.value) return
  emit('save', {
    opening_balance_k: b,
    opening_balance_date: balanceDate.value,
    reserve_k: isNaN(r) ? 5 : r,
  })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" data-testid="settings.root" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div data-testid="settings.backdrop" class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="$emit('close')" />
        <UiModalPanel size="sm" labelled-by="settings-modal-title" class="modal-panel relative">
          <template #header>
            <h2 id="settings-modal-title" class="text-base font-semibold text-fg">Liquidity Settings</h2>
          </template>

          <div class="space-y-4">
            <UiField>
              <template #label>Opening Balance ($k)</template>
              <template #default="{ id, describedBy }">
                <div class="relative">
                  <input
                    data-testid="settings.balance"
                    v-model="balanceK"
                    :id="id"
                    :aria-describedby="describedBy"
                    type="number"
                    step="0.01"
                    class="ui-input pr-8 text-lg tabular"
                  />
                  <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fg-muted">k</span>
                </div>
              </template>
              <template #helper>Balance at start of the anchor date. e.g. 49 = $49,000</template>
            </UiField>

            <UiField>
              <template #label>As-of Date</template>
              <template #default="{ id, describedBy }">
                <input
                  data-testid="settings.date"
                  v-model="balanceDate"
                  :id="id"
                  :aria-describedby="describedBy"
                  type="date"
                  class="ui-input"
                />
              </template>
            </UiField>

            <UiField>
              <template #label>Reserve Threshold ($k)</template>
              <template #default="{ id, describedBy }">
                <div class="relative">
                  <input
                    data-testid="settings.reserve"
                    v-model="reserveK"
                    :id="id"
                    :aria-describedby="describedBy"
                    type="number"
                    step="0.1"
                    min="0"
                    class="ui-input pr-8 tabular"
                  />
                  <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fg-muted">k</span>
                </div>
              </template>
              <template #helper>Soft warning if balance drops below this. Default: 5k</template>
            </UiField>
          </div>

          <template #footer>
            <div class="flex flex-wrap justify-end gap-3">
              <UiButton data-testid="settings.cancel" variant="ghost" @click="$emit('close')">
                Cancel
              </UiButton>
              <UiButton data-testid="settings.save" variant="primary" @click="onSave">
                Save
              </UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active {
  transition: opacity var(--dur-fast) var(--ease-standard);
}
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-panel, .modal-leave-active .modal-panel {
  transition: transform var(--dur-fast) var(--ease-standard);
}
.modal-enter-from .modal-panel, .modal-leave-to .modal-panel { transform: scale(0.97); }
</style>
