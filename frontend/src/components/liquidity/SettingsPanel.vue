<script setup lang="ts">
import { ref, watch } from 'vue'
import type { LiquiditySettings } from '../../types/liquidity'

const props = defineProps<{
  open: boolean
  settings: LiquiditySettings
}>()

/** The soft-warning threshold of a fresh install (the backend's default). */
const DEFAULT_RESERVE_DOLLARS = 5000

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: { opening_balance_dollars: number; opening_balance_date: string; reserve_dollars: number }): void
}>()

const openingBalanceDollars = ref('')
const balanceDate = ref('')
const reserveDollars = ref('')

watch(() => props.open, (open) => {
  if (!open) return
  openingBalanceDollars.value = props.settings.opening_balance_dollars.toString()
  balanceDate.value = props.settings.opening_balance_date
  reserveDollars.value = props.settings.reserve_dollars.toString()
})

function onSave() {
  const b = parseFloat(openingBalanceDollars.value)
  const r = parseFloat(reserveDollars.value)
  if (isNaN(b) || !balanceDate.value) return
  emit('save', {
    opening_balance_dollars: b,
    opening_balance_date: balanceDate.value,
    reserve_dollars: isNaN(r) ? DEFAULT_RESERVE_DOLLARS : r,
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
            <h2 id="settings-modal-title" class="flex items-center gap-2.5 font-display text-lg font-semibold tracking-display text-fg">
              <span class="grid h-8 w-8 place-items-center rounded-ctl bg-primary/12 text-primary" aria-hidden="true"><i class="pi pi-cog text-xs"></i></span>
              Liquidity Settings
            </h2>
          </template>

          <div class="space-y-4">
            <UiField>
              <template #label>Opening Balance ($)</template>
              <template #default="{ id, describedBy }">
                <div class="relative">
                  <input
                    data-testid="settings.balance"
                    v-model="openingBalanceDollars"
                    :id="id"
                    :aria-describedby="describedBy"
                    type="number"
                    step="0.01"
                    class="ui-input numeric pl-7"
                  />
                  <span class="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-fg-muted">$</span>
                </div>
              </template>
              <template #helper>Balance at start of the anchor date, in exact dollars (e.g. 49000)</template>
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
              <template #label>Reserve Threshold ($)</template>
              <template #default="{ id, describedBy }">
                <div class="relative">
                  <input
                    data-testid="settings.reserve"
                    v-model="reserveDollars"
                    :id="id"
                    :aria-describedby="describedBy"
                    type="number"
                    step="1"
                    min="0"
                    class="ui-input numeric pl-7"
                  />
                  <span class="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-fg-muted">$</span>
                </div>
              </template>
              <template #helper>Soft warning if balance drops below this. Default: $5,000</template>
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
