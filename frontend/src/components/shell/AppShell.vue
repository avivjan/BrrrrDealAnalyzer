<script setup lang="ts">
/**
 * The persistent frame every route renders inside.
 *
 * Desktop (`lg+`): a two-column grid — sidebar | topbar over `<main>` — where
 * `<main>` is the one page scroller. Phone: topbar, `<main>`, fixed bottom nav.
 * The shell owns three pieces of presentational state, all per browser:
 * whether the sidebar is collapsed (`localStorage['bw.sidebar']`), whether the
 * command palette is open (`Cmd/Ctrl+K`), and whether Settings is open.
 * Nothing here fetches or touches a store; `App.vue`'s `onMounted` still does
 * exactly what it did.
 *
 * The sidebar's width is `--sidebar-w` on this root, swapped instantly when
 * collapsed: an animated width would make the liquidity chart's
 * ResizeObserver repaint through the whole transition.
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { cn } from "../../design/cn";
import AppMobileNav from "./AppMobileNav.vue";
import AppSettings from "./AppSettings.vue";
import AppSidebar from "./AppSidebar.vue";
import AppTopbar from "./AppTopbar.vue";
import CommandPalette from "./CommandPalette.vue";
import { navItemForPath } from "./nav";

const SIDEBAR_STORAGE_KEY = "bw.sidebar";

function readCollapsed(): boolean {
  try {
    return typeof localStorage !== "undefined" && localStorage.getItem(SIDEBAR_STORAGE_KEY) === "collapsed";
  } catch {
    return false;
  }
}

const collapsed = ref(readCollapsed());
const paletteOpen = ref(false);
const settingsOpen = ref(false);

function setCollapsed(value: boolean) {
  collapsed.value = value;
  try {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, value ? "collapsed" : "expanded");
  } catch {
    // Remembering the choice is a convenience, not a requirement.
  }
}

const route = useRoute();
const title = computed(() => navItemForPath(route.path)?.title ?? "BigWhales");

function onKeydown(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    paletteOpen.value = !paletteOpen.value;
  }
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));

const rootClass = computed(() =>
  cn(
    "app-shell relative grid h-dvh grid-rows-[auto_1fr] bg-page font-sans text-fg selection:bg-primary selection:text-primary-fg",
    "lg:grid-cols-[var(--sidebar-w)_1fr]",
  ),
);
</script>

<template>
  <div :class="rootClass" :data-collapsed="collapsed || undefined">
    <a
      href="#main"
      class="sr-only z-50 rounded-ctl bg-primary px-3 py-2 text-primary-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
    >
      Skip to content
    </a>

    <AppSidebar
      class="hidden lg:row-span-2 lg:flex"
      :collapsed="collapsed"
      @update:collapsed="setCollapsed"
      @open-settings="settingsOpen = true"
    />

    <AppTopbar :title="title" @open-settings="settingsOpen = true" @open-palette="paletteOpen = true" />

    <!--
      The only page scroller. `min-h-0` lets it shrink inside the grid row so a
      view taller than the screen scrolls here, not the document; the bottom
      padding keeps the last line clear of the phone's bottom nav.
    -->
    <main
      id="main"
      class="relative min-h-0 overflow-y-auto overscroll-contain pb-[calc(4.25rem+env(safe-area-inset-bottom))] lg:pb-0"
    >
      <slot />
    </main>

    <AppMobileNav class="lg:hidden" />

    <CommandPalette :open="paletteOpen" @close="paletteOpen = false" @open-settings="settingsOpen = true" />
    <AppSettings :open="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>

<style scoped>
/* The collapsed sidebar is a narrower column, switched — never transitioned. */
.app-shell[data-collapsed] {
  --sidebar-w: var(--sidebar-w-collapsed);
}

/* `dvh` fallback for iOS 15.0–15.3 (inside this project's browserslist). */
@supports not (height: 100dvh) {
  .app-shell {
    height: 100vh;
  }
}
</style>
