<script setup lang="ts">
/**
 * "This changes the liquidity timeline" (tasks/todo/ConstructionAccountPerRehab.md): the figures and the deal's rows
 * before -> after, and the rows you edited by hand that the change disagrees with ("Use ..." takes the new value).
 * Confirm saves; Cancel saves nothing. A change the bank reported was already applied: it shows with OK only.
 * One instance, in the app shell; the store decides what it shows.
 */
import { computed } from 'vue'

import { useLiquidityTimelineChangePromptStore } from '../../stores/liquidityTimelineChangePromptStore'
import DealCashRowChangesList from './DealCashRowChangesList.vue'

const promptStore = useLiquidityTimelineChangePromptStore()
const current = computed(() => promptStore.open)
const title = computed(() => current.value?.request?.title ?? current.value?.bankReport?.title ?? '')
const address = computed(() => current.value?.preview?.rowChanges?.deal_address ?? '')
const changes = computed(() => current.value?.preview?.rowChanges?.changes ?? [])
const figureChanges = computed(() => current.value?.preview?.figureChanges ?? [])
const rowsMarkedDone = computed(() => current.value?.preview?.rowDescriptionsMarkedDone ?? [])
const pendingAfterThisOne = computed(() => promptStore.queue.length)

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && !current.value?.isConfirming) promptStore.cancel()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="current" data-testid="timeline-prompt.root" class="fixed inset-0 z-[60] flex items-center justify-center p-4" @keydown="onKeydown">
        <div class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="!current.isConfirming && promptStore.cancel()" />
        <UiModalPanel size="lg" labelled-by="timeline-prompt-title" class="modal-panel relative">
          <template #header>
            <div>
              <h2 id="timeline-prompt-title" class="flex items-center gap-2.5 font-display text-lg font-semibold tracking-display text-fg">
                <span class="grid h-8 w-8 place-items-center rounded-ctl bg-primary/12 text-primary" aria-hidden="true">
                  <i :class="promptStore.isABankReport ? 'pi pi-building-columns text-xs' : 'pi pi-chart-line text-xs'"></i>
                </span>
                {{ promptStore.isABankReport ? 'Timeline updated from the bank' : 'This changes the liquidity timeline' }}
              </h2>
              <p data-testid="timeline-prompt.subtitle" class="mt-1 text-sm text-fg-muted">
                {{ title }}<template v-if="address"> · {{ address }}</template>
              </p>
            </div>
          </template>

          <div class="space-y-4">
            <p v-if="current.isLoading && !current.preview" data-testid="timeline-prompt.loading" class="text-sm text-fg-muted">Reading what this changes…</p>
            <p v-if="current.errorMessage" data-testid="timeline-prompt.error" role="alert" class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
              {{ current.errorMessage }}
            </p>

            <section v-if="figureChanges.length" data-testid="timeline-prompt.figures" aria-label="Figures that change">
              <h3 class="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Figures</h3>
              <ul class="divide-y divide-line rounded-ctl border border-line">
                <li v-for="figure in figureChanges" :key="figure.label" :data-testid="`timeline-prompt.figure.${figure.label}`"
                    class="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                  <span class="text-fg">{{ figure.label }}</span>
                  <span class="numeric text-fg-muted"><s>{{ figure.before || '—' }}</s> <i class="pi pi-arrow-right mx-1 text-[10px]" aria-hidden="true"></i><span class="font-semibold text-fg">{{ figure.after || '—' }}</span></span>
                </li>
              </ul>
            </section>

            <section v-if="rowsMarkedDone.length" data-testid="timeline-prompt.marked-done" aria-label="Rows marked done">
              <h3 class="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Marked done</h3>
              <ul class="space-y-1 text-sm text-fg">
                <li v-for="description in rowsMarkedDone" :key="description"><i class="pi pi-check mr-1.5 text-xs text-positive" aria-hidden="true"></i>{{ description }}</li>
              </ul>
            </section>

            <section v-if="changes.length" aria-label="Timeline rows">
              <h3 class="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Timeline rows</h3>
              <DealCashRowChangesList
                :changes="changes"
                :use-deal-value-for="current.useTheNewValueFor"
                @update:use-deal-value-for="promptStore.setUseTheNewValueFor"
              />
            </section>
          </div>

          <template #footer>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <span v-if="pendingAfterThisOne" data-testid="timeline-prompt.pending" class="text-xs text-fg-muted">
                {{ pendingAfterThisOne }} more {{ pendingAfterThisOne === 1 ? 'change waits' : 'changes wait' }} after this one
              </span>
              <span v-else></span>
              <div class="flex gap-3">
                <template v-if="promptStore.isABankReport">
                  <UiButton data-testid="timeline-prompt.ok" variant="primary" @click="promptStore.confirm()">OK</UiButton>
                </template>
                <template v-else>
                  <UiButton data-testid="timeline-prompt.cancel" variant="ghost" :disabled="current.isConfirming" @click="promptStore.cancel()">Cancel</UiButton>
                  <UiButton data-testid="timeline-prompt.confirm" variant="primary" :disabled="current.isConfirming || current.isLoading || !current.preview"
                            @click="promptStore.confirm()">
                    {{ current.isConfirming ? 'Saving…' : 'Confirm' }}
                  </UiButton>
                </template>
              </div>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity var(--dur-fast) var(--ease-standard); }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
