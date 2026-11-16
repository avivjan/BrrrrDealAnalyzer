<script setup lang="ts">
/**
 * HTML to Drive (tasks/todo/DealDriveFolderRehabSummaryAndProjection.md): saves the Bought deal's interactive HTML report
 * in the deal's own Google Drive folder as "<date> deal projection.html", after any pending edit is saved.
 */
import { ref } from 'vue'

import api from '../../api'
import { todayISO } from '../../utils/liquidityEngine'
import { safeHref } from '../../utils/safeHref'

const props = defineProps<{
  dealId: string
  dealType: 'BRRRR' | 'FLIP'
  /** False while the deal has no valid Drive folder link: the button explains instead of sending. */
  hasAValidDriveFolderLink: boolean
  savePendingEdits: () => Promise<void>
}>()

const isSaving = ref(false)
const savedFileName = ref<string | null>(null)
const savedFolderUrl = ref<string | null>(null)
const errorMessage = ref<string | null>(null)

async function saveToDrive() {
  savedFileName.value = null
  errorMessage.value = null
  if (!props.hasAValidDriveFolderLink) {
    errorMessage.value = 'Add the deal\'s Google Drive folder link first.'
    return
  }
  isSaving.value = true
  try {
    await props.savePendingEdits()
    const saved = await api.saveBoughtDealProjectionToDrive(props.dealId, props.dealType, todayISO())
    savedFileName.value = saved.file_name
    savedFolderUrl.value = saved.drive_folder_url
  } catch (error) {
    const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
    errorMessage.value = typeof detail === 'string' ? detail : 'The projection could not be saved to Drive. Try again in a moment.'
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-1">
    <UiButton variant="secondary" size="sm" data-testid="boughtdeals.modal.html-to-drive" :loading="isSaving" class="self-start" @click="saveToDrive">
      <i class="pi pi-cloud-upload mr-1.5 text-xs" aria-hidden="true"></i>HTML to Drive
    </UiButton>
    <p v-if="savedFileName" data-testid="boughtdeals.modal.html-to-drive.saved" role="status" class="text-xs text-positive">
      Saved "{{ savedFileName }}" in the deal's Drive folder.
      <a v-if="savedFolderUrl" :href="safeHref(savedFolderUrl)" target="_blank" rel="noopener noreferrer" class="underline">Open the folder</a>
    </p>
    <p v-if="errorMessage" data-testid="boughtdeals.modal.html-to-drive.error" role="alert" class="text-xs text-negative">{{ errorMessage }}</p>
  </div>
</template>
