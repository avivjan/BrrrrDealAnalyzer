<script setup lang="ts">
/**
 * The `?` sheet: every keyboard shortcut in one list (tasks/todo/ConstructionAccountPerRehab.md, Step C0). The
 * go-to keys come from `shell/nav.ts`, so the sheet can never list a key the app does not answer.
 */
import { NAV_ITEMS } from './nav'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const OTHER_SHORTCUTS: { keys: string[]; what: string }[] = [
  { keys: ['⌘', 'K'], what: 'Search pages, deals and settings (Ctrl K on Windows)' },
  { keys: ['?'], what: 'This list' },
  { keys: ['Esc'], what: 'Close a window' },
]
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" data-testid="shell.shortcuts" class="fixed inset-0 z-50 flex items-center justify-center p-4" @keydown.escape="emit('close')">
        <div class="absolute inset-0 bg-fg/50 md:backdrop-blur-sm" @click="emit('close')" />
        <UiModalPanel size="md" labelled-by="shell-shortcuts-title" class="modal-panel relative">
          <template #header>
            <h2 id="shell-shortcuts-title" class="font-display text-lg font-semibold tracking-display text-fg">Keyboard shortcuts</h2>
          </template>
          <div class="space-y-4 text-sm">
            <section aria-labelledby="shell-shortcuts-go-to">
              <h3 id="shell-shortcuts-go-to" class="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">Go to, outside a text field</h3>
              <ul class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                <li v-for="item in NAV_ITEMS" :key="item.name" :data-testid="`shell.shortcuts.go-to.${item.goToKey}`" class="flex items-center gap-2">
                  <kbd class="rounded border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-xs">g</kbd>
                  <kbd class="rounded border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-xs">{{ item.goToKey }}</kbd>
                  <span class="text-fg">{{ item.title }}</span>
                </li>
              </ul>
            </section>
            <section aria-labelledby="shell-shortcuts-other">
              <h3 id="shell-shortcuts-other" class="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-fg-muted">Anywhere</h3>
              <ul class="space-y-1.5">
                <li v-for="shortcut in OTHER_SHORTCUTS" :key="shortcut.what" class="flex items-center gap-2">
                  <kbd v-for="key in shortcut.keys" :key="key" class="rounded border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-xs">{{ key }}</kbd>
                  <span class="text-fg">{{ shortcut.what }}</span>
                </li>
              </ul>
            </section>
          </div>
          <template #footer>
            <div class="flex justify-end">
              <UiButton variant="secondary" data-testid="shell.shortcuts.close" @click="emit('close')">Close</UiButton>
            </div>
          </template>
        </UiModalPanel>
      </div>
    </Transition>
  </Teleport>
</template>
