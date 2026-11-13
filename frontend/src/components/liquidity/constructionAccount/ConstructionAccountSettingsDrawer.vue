<script setup lang="ts">
/**
 * Every construction account setting, edited here and stored in the database (tasks/todo/ConstructionAccountPerRehab.md,
 * Requirement 3), and the Mercury connection per LLC: which token settings the backend found, the exact name to add for
 * a missing one, and how instant updates are doing. Never a token's value.
 */
import { computed, ref, watch } from 'vue'

import { liquidityApi } from '../../../api/liquidity'
import { useConstructionAccountStore } from '../../../stores/constructionAccountStore'
import { useLiquidityTimelineChangePromptStore } from '../../../stores/liquidityTimelineChangePromptStore'
import type { LiquiditySettings } from '../../../types/liquidity'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'saved', settings: LiquiditySettings): void }>()

const store = useConstructionAccountStore()
const promptStore = useLiquidityTimelineChangePromptStore()
const refreshIntervalSeconds = ref('30')
const refreshWhenWindowRegainsFocus = ref(true)
const inAppTransfersEnabled = ref(true)
const transfersPerHourLimit = ref('5')
const maximumSingleTransferDollars = ref('100000')
const newWorkspaceLabel = ref('')
const errorMessage = ref<string | null>(null)
const isSaving = ref(false)
const copiedName = ref<string | null>(null)

const connection = computed(() => store.connectionStatus)
const newLabel = computed(() => newWorkspaceLabel.value.trim().toUpperCase().replace(/[^A-Z0-9_]/g, ''))

watch(() => props.open, async (open) => {
  if (!open) return
  errorMessage.value = null
  try {
    const [settings] = await Promise.all([liquidityApi.getSettings(), store.loadConnectionStatus()])
    refreshIntervalSeconds.value = String(settings.construction_account_refresh_interval_seconds ?? 30)
    refreshWhenWindowRegainsFocus.value = settings.construction_account_refresh_when_window_regains_focus ?? true
    inAppTransfersEnabled.value = settings.construction_account_in_app_transfers_enabled ?? true
    transfersPerHourLimit.value = String(settings.construction_account_transfers_per_hour_limit ?? 5)
    maximumSingleTransferDollars.value = String(settings.construction_account_maximum_single_transfer_dollars ?? 100000)
  } catch {
    errorMessage.value = 'The settings could not be read.'
  }
})

async function save() {
  const interval = Math.round(Number(refreshIntervalSeconds.value))
  const perHour = Math.round(Number(transfersPerHourLimit.value))
  const maximum = Number(maximumSingleTransferDollars.value)
  if (!(interval >= 15 && interval <= 600) || !(perHour >= 1 && perHour <= 60) || !(maximum > 0)) {
    errorMessage.value = 'Refresh every 15 to 600 seconds, 1 to 60 transfers an hour, and a maximum above $0.'
    return
  }
  isSaving.value = true
  errorMessage.value = null
  try {
    const saved = await liquidityApi.updateSettings({
      construction_account_refresh_interval_seconds: interval,
      construction_account_refresh_when_window_regains_focus: refreshWhenWindowRegainsFocus.value,
      construction_account_in_app_transfers_enabled: inAppTransfersEnabled.value,
      construction_account_transfers_per_hour_limit: perHour,
      construction_account_maximum_single_transfer_dollars: maximum,
    })
    promptStore.showSaved('Settings saved')
    emit('saved', saved)
    emit('close')
  } catch {
    errorMessage.value = 'The settings could not be saved.'
  } finally {
    isSaving.value = false
  }
}

async function copy(name: string) {
  try {
    await navigator.clipboard.writeText(name)
    copiedName.value = name
  } catch {
    copiedName.value = null
  }
}

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`
  return new Date(iso).toLocaleDateString()
}
</script>

<template>
  <UiDrawer :open="open" side="right" size="md" data-testid="ca-settings.root" @close="emit('close')">
    <template #header>Construction account settings</template>
    <div class="space-y-6">
      <p v-if="errorMessage" data-testid="ca-settings.error" role="alert" class="rounded-ctl border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">{{ errorMessage }}</p>

      <section class="space-y-3" aria-label="Live updates">
        <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Live updates from Mercury</h3>
        <UiField>
          <template #label>Re-read Mercury every (seconds)</template>
          <template #default="{ id }"><input :id="id" v-model="refreshIntervalSeconds" data-testid="ca-settings.refresh-interval" type="number" min="15" max="600" step="1" class="ui-input numeric" /></template>
          <template #helper>While this page or the timeline is open. 15 to 600.</template>
        </UiField>
        <label class="flex items-center gap-2 text-sm text-fg">
          <input v-model="refreshWhenWindowRegainsFocus" data-testid="ca-settings.refresh-on-focus" type="checkbox" class="h-4 w-4 accent-primary" />
          Re-read at once when I come back to the window
        </label>
      </section>

      <section class="space-y-3" aria-label="Transfers">
        <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Deposit and Steal in the app</h3>
        <label class="flex items-center gap-2 text-sm text-fg">
          <input v-model="inAppTransfersEnabled" data-testid="ca-settings.transfers-enabled" type="checkbox" class="h-4 w-4 accent-primary" />
          Allow transfers from the app
        </label>
        <div class="grid grid-cols-2 gap-3">
          <UiField>
            <template #label>Per hour, at most</template>
            <template #default="{ id }"><input :id="id" v-model="transfersPerHourLimit" data-testid="ca-settings.transfers-per-hour" type="number" min="1" max="60" class="ui-input numeric" /></template>
          </UiField>
          <UiField>
            <template #label>Largest transfer ($)</template>
            <template #default="{ id }"><input :id="id" v-model="maximumSingleTransferDollars" data-testid="ca-settings.maximum-transfer" type="number" min="1" step="1" class="ui-input numeric" /></template>
          </UiField>
        </div>
      </section>

      <section class="space-y-3" aria-label="Mercury connection" data-testid="ca-settings.connection">
        <h3 class="text-xs font-medium uppercase tracking-[0.12em] text-fg-muted">Mercury connection, per LLC</h3>
        <p class="text-xs text-fg-muted">
          Tokens are kept in the hosting dashboard's secret settings, never in the app. A missing one shows the exact name to add there.
        </p>
        <ul class="space-y-2">
          <li v-for="workspace in connection?.workspaces ?? []" :key="workspace.mercury_workspace_label"
              :data-testid="`ca-settings.workspace.${workspace.mercury_workspace_label}`" class="space-y-1.5 rounded-ctl border border-line p-3 text-sm">
            <p class="font-medium text-fg">{{ workspace.mercury_workspace_label }}</p>
            <p class="flex flex-wrap items-center gap-2">
              <UiBadge :tone="workspace.has_read_token ? 'positive' : 'negative'">Read token {{ workspace.has_read_token ? 'found' : 'missing' }}</UiBadge>
              <UiBadge :tone="workspace.has_transfer_token ? 'positive' : 'warning'">Transfer token {{ workspace.has_transfer_token ? 'found' : 'missing' }}</UiBadge>
            </p>
            <p v-if="!workspace.has_read_token" class="text-xs text-fg-muted">
              Add <code :data-testid="`ca-settings.workspace.${workspace.mercury_workspace_label}.read-name`" class="rounded bg-surface-3 px-1">{{ workspace.read_token_environment_variable_name }}</code>
              <button type="button" class="ml-1 underline" @click="copy(workspace.read_token_environment_variable_name)">{{ copiedName === workspace.read_token_environment_variable_name ? 'Copied' : 'Copy' }}</button>
            </p>
            <p v-if="!workspace.has_transfer_token" class="text-xs text-fg-muted">
              For Deposit and Steal, add <code :data-testid="`ca-settings.workspace.${workspace.mercury_workspace_label}.transfer-name`" class="rounded bg-surface-3 px-1">{{ workspace.transfer_token_environment_variable_name }}</code>
              <button type="button" class="ml-1 underline" @click="copy(workspace.transfer_token_environment_variable_name)">{{ copiedName === workspace.transfer_token_environment_variable_name ? 'Copied' : 'Copy' }}</button>
            </p>
            <p :data-testid="`ca-settings.workspace.${workspace.mercury_workspace_label}.instant`" class="text-xs text-fg-muted">
              Instant updates: {{ workspace.instant_updates_are_on ? 'on' : 'off' }}<template v-if="workspace.instant_updates_are_on">
                · {{ workspace.last_valid_event_received_at ? `last instant event ${timeAgo(workspace.last_valid_event_received_at)}` : 'waiting for the first event' }}</template>
            </p>
            <p v-if="workspace.last_webhook_error_message" :data-testid="`ca-settings.workspace.${workspace.mercury_workspace_label}.error`" class="text-xs text-negative">
              {{ workspace.last_webhook_error_message }} ({{ timeAgo(workspace.last_webhook_error_at) }})
            </p>
          </li>
        </ul>
        <div class="space-y-1.5 rounded-ctl border border-dashed border-line p-3">
          <label class="flex flex-col gap-1 text-xs text-fg-muted">Adding another LLC? Its label
            <input v-model="newWorkspaceLabel" data-testid="ca-settings.new-label" type="text" maxlength="40" placeholder="e.g. AJYK" class="ui-input text-sm uppercase" />
          </label>
          <p v-if="newLabel" data-testid="ca-settings.new-label-names" class="text-xs text-fg-muted">
            Add <code class="rounded bg-surface-3 px-1">MERCURY_API_TOKEN_{{ newLabel }}</code> (a read-only token) and, for transfers,
            <code class="rounded bg-surface-3 px-1">MERCURY_TRANSFER_API_TOKEN_{{ newLabel }}</code> to the hosting dashboard, then redeploy.
          </p>
        </div>
      </section>
    </div>
    <template #footer>
      <div class="flex justify-end gap-3">
        <UiButton variant="ghost" data-testid="ca-settings.cancel" @click="emit('close')">Cancel</UiButton>
        <UiButton data-testid="ca-settings.save" :loading="isSaving" @click="save">Save</UiButton>
      </div>
    </template>
  </UiDrawer>
</template>
