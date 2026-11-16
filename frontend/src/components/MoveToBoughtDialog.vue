<script setup lang="ts">
/**
 * Move to Bought asks for the deal's own Google Drive folder (tasks/todo/DealDriveFolderRehabSummaryAndProjection.md):
 * the rehab summary and "HTML to Drive" save there. Prefilled from the deal; the server checks it again.
 */
import { computed, ref, watch } from 'vue'

import { GOOGLE_DRIVE_FOLDER_LINK_EXAMPLE, googleDriveFolderLinkProblem } from '../utils/googleDriveFolderLink'

const props = defineProps<{
  open: boolean
  dealAddress: string
  initialGoogleDriveLink: string | null | undefined
  isMoving: boolean
  /** The server's answer when it refused the move. */
  serverErrorMessage: string | null
}>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'confirm', googleDriveLink: string): void
}>()

const googleDriveLink = ref('')
const hasTriedToConfirm = ref(false)
watch(() => props.open, (isOpen) => {
  if (!isOpen) return
  googleDriveLink.value = (props.initialGoogleDriveLink ?? '').trim()
  hasTriedToConfirm.value = false
}, { immediate: true })

const linkProblem = computed(() => googleDriveFolderLinkProblem(googleDriveLink.value))
const shownLinkProblem = computed(() => (hasTriedToConfirm.value || googleDriveLink.value ? linkProblem.value : null))

function confirm() {
  hasTriedToConfirm.value = true
  if (linkProblem.value) return
  emit('confirm', googleDriveLink.value.trim())
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" data-testid="move-to-bought.root" class="fixed inset-0 z-50 flex items-center justify-center p-4" @keydown.escape="emit('cancel')">
        <div class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="emit('cancel')" />
        <UiModalPanel size="md" labelled-by="move-to-bought-title" class="modal-panel relative">
          <template #header>
            <div>
              <h2 id="move-to-bought-title" class="font-display text-lg font-semibold tracking-display text-fg">Move to Bought Deals</h2>
              <p class="mt-1 text-sm text-fg-muted">{{ dealAddress }}. A copy is created in the Bought Deals pipeline.</p>
            </div>
          </template>
          <div class="space-y-3">
            <UiField>
              <template #label>Google Drive Link (the deal's folder)</template>
              <template #default="{ id, describedBy }">
                <input :id="id" v-model="googleDriveLink" data-testid="move-to-bought.google-drive-link" type="url" inputmode="url" autocomplete="off"
                       :placeholder="GOOGLE_DRIVE_FOLDER_LINK_EXAMPLE" :aria-describedby="describedBy" :aria-invalid="shownLinkProblem ? 'true' : undefined"
                       class="ui-input" @keydown.enter.prevent="confirm" />
              </template>
              <template #helper>A Google Drive folder you own. The rehab summary is saved in its "Rehab" subfolder, and "HTML to Drive" saves the deal projection there.</template>
            </UiField>
            <p v-if="shownLinkProblem" data-testid="move-to-bought.link-problem" role="alert" class="text-sm text-negative">{{ shownLinkProblem }}</p>
            <p v-if="serverErrorMessage" data-testid="move-to-bought.error" role="alert"
               class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">{{ serverErrorMessage }}</p>
          </div>
          <template #footer>
            <div class="flex justify-end gap-3">
              <UiButton variant="ghost" data-testid="move-to-bought.cancel" @click="emit('cancel')">Cancel</UiButton>
              <UiButton data-testid="move-to-bought.confirm" :loading="isMoving" @click="confirm">Move to Bought</UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </Transition>
  </Teleport>
</template>
