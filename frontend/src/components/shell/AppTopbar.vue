<script setup lang="ts">
/**
 * The page header: the route's title, the palette trigger, the mode toggle,
 * the Appearance gear and the connection status. Mounted on every route,
 * including REPS, which is why it also hosts `app.status`.
 */
import CommandTrigger from "./CommandTrigger.vue";
import ConnectionStatus from "./ConnectionStatus.vue";
import SettingsTrigger from "./SettingsTrigger.vue";
import ThemeToggle from "./ThemeToggle.vue";

withDefaults(defineProps<{ title?: string }>(), { title: "BigWhales" });
const emit = defineEmits<{ openSettings: []; openPalette: [] }>();
</script>

<template>
  <header
    data-testid="shell.topbar"
    class="glass sticky top-0 z-30 flex min-h-topbar items-center gap-3 rounded-none border-x-0 border-t-0 border-b-ui border-line/60 px-3 pt-[max(0px,env(safe-area-inset-top))] sm:px-5 lg:static"
  >
    <span aria-hidden="true" class="grid h-8 w-8 shrink-0 place-items-center rounded-ctl bg-brand text-primary-fg lg:hidden">
      <i class="pi pi-bolt text-sm" />
    </span>
    <h1 class="min-w-0 flex-1 truncate font-display text-lg font-semibold tracking-display text-fg">{{ title }}</h1>
    <div class="flex items-center gap-1.5 sm:gap-2">
      <slot name="actions" />
      <CommandTrigger @click="emit('openPalette')" />
      <UiIconButton
        data-testid="shell.command-trigger-mobile"
        size="md"
        label="Search or jump to"
        class="md:hidden"
        @click="emit('openPalette')"
      >
        <i class="pi pi-search" aria-hidden="true" />
      </UiIconButton>
      <ThemeToggle />
      <SettingsTrigger @click="emit('openSettings')" />
      <ConnectionStatus />
    </div>
  </header>
</template>
