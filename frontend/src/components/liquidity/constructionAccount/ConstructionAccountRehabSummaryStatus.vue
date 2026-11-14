<script setup lang="ts">
/**
 * The rehab summary of a closed-out construction account (tasks/todo/ConstructionAccountsCompactCardsAndRehabSummary.md):
 * whether it was e-mailed and saved to Drive, its PDF and CSV to download, and Send again.
 */
import { computed, ref } from 'vue'

import { constructionAccountApi } from '../../../api/constructionAccount'
import { useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import type { ConstructionAccountStatus } from '../../../types/constructionAccount'

const props = defineProps<{ status: ConstructionAccountStatus }>()
const emit = defineEmits<{ (e: 'error', message: string): void }>()

const store = useConstructionAccountStore()
const busyAction = ref<'send-again' | 'pdf' | 'csv' | null>(null)
const hook = (name: string) => `ca.${props.status.bought_deal_id}.rehab-summary.${name}`
const latestRehabSummary = computed(() => props.status.latest_rehab_summary ?? null)

const DELIVERY_STATE_LABELS = {
  sending: 'Being e-mailed and saved to Drive…',
  delivered: 'E-mailed to you and saved to your Google Drive',
  will_retry: 'Not delivered yet: it is tried again every 30 minutes',
  failed: 'Not delivered after 3 tries: use Send again',
} as const
const DELIVERY_STATE_TONES = { sending: 'neutral', delivered: 'positive', will_retry: 'warning', failed: 'negative' } as const

function channelText(channelStatus: 'pending' | 'delivered' | 'failed', errorTypeName: string | null): string {
  if (channelStatus === 'delivered') return '✓'
  if (channelStatus === 'failed') return `not yet${errorTypeName ? ` (${errorTypeName})` : ''}`
  return '…'
}

function errorMessageOf(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function sendAgain() {
  busyAction.value = 'send-again'
  try {
    await constructionAccountApi.sendRehabSummaryAgain(props.status.bought_deal_id)
    await store.load()
  } catch (error) {
    emit('error', errorMessageOf(error, 'The summary could not be sent again. Try again in a moment.'))
  } finally {
    busyAction.value = null
  }
}

async function download(fileKind: 'pdf' | 'csv') {
  if (!latestRehabSummary.value) return
  busyAction.value = fileKind
  try {
    const blob = await constructionAccountApi.rehabSummaryFile(props.status.bought_deal_id, latestRehabSummary.value.rehab_summary_id, fileKind)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `Rehab summary ${props.status.deal_address}${fileKind === 'csv' ? ' transactions' : ''}.${fileKind}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch {
    emit('error', 'The file could not be downloaded. Try again in a moment.')
  } finally {
    busyAction.value = null
  }
}
</script>

<template>
  <section :data-testid="hook('root')" aria-label="Rehab summary" class="space-y-2 rounded-ctl border border-line p-3">
    <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Rehab summary</h3>
    <template v-if="latestRehabSummary">
      <p class="flex flex-wrap items-center gap-2 text-sm">
        <UiBadge :data-testid="hook('state')" :data-state="latestRehabSummary.overall_delivery_state" :tone="DELIVERY_STATE_TONES[latestRehabSummary.overall_delivery_state]">
          {{ DELIVERY_STATE_LABELS[latestRehabSummary.overall_delivery_state] }}
        </UiBadge>
        <span class="text-xs text-fg-muted">
          e-mail {{ channelText(latestRehabSummary.email_delivery_status, latestRehabSummary.email_last_error_type_name) }} ·
          Drive {{ channelText(latestRehabSummary.drive_delivery_status, latestRehabSummary.drive_last_error_type_name) }} ·
          made {{ new Date(latestRehabSummary.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) }}
        </span>
      </p>
      <div class="flex flex-wrap gap-2">
        <UiButton variant="secondary" size="sm" :data-testid="hook('download-pdf')" :loading="busyAction === 'pdf'" @click="download('pdf')">
          <i class="pi pi-file-pdf mr-1.5 text-xs" aria-hidden="true"></i>Download PDF
        </UiButton>
        <UiButton variant="ghost" size="sm" :data-testid="hook('download-csv')" :loading="busyAction === 'csv'" @click="download('csv')">Download CSV</UiButton>
        <a v-if="latestRehabSummary.drive_folder_url" :data-testid="hook('drive-folder')" :href="latestRehabSummary.drive_folder_url" target="_blank" rel="noopener noreferrer"
           class="inline-flex items-center gap-1 rounded-ctl px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">
          <i class="pi pi-folder-open text-[10px]" aria-hidden="true"></i>Open the Drive folder
        </a>
        <UiButton variant="ghost" size="sm" :data-testid="hook('send-again')" :loading="busyAction === 'send-again'" @click="sendAgain">Send again</UiButton>
      </div>
    </template>
    <template v-else>
      <p class="text-xs text-fg-muted">No summary yet. One is made when you close the account out.</p>
      <UiButton variant="ghost" size="sm" :data-testid="hook('send-again')" :loading="busyAction === 'send-again'" @click="sendAgain">Make and send it now</UiButton>
    </template>
  </section>
</template>
