<script setup lang="ts">
/**
 * The desktop sidebar: wordmark, primary nav with a sliding active indicator,
 * and a footer with the collapse toggle and the Appearance gear.
 *
 * Collapsing changes `--sidebar-w` on the shell root instantly — no width
 * transition — because the liquidity chart's ResizeObserver must never watch
 * an animated ancestor. The indicator moves with a CSS transform transition
 * (Phase 4 may hand it to GSAP); its position is the active item's index.
 */
import { computed } from "vue";
import { useRoute } from "vue-router";

import { cn } from "../../design/cn";
import { NAV_ITEMS } from "./nav";
import NavItem from "./NavItem.vue";

const props = withDefaults(defineProps<{ collapsed?: boolean }>(), { collapsed: false });
const emit = defineEmits<{ "update:collapsed": [value: boolean]; openSettings: [] }>();

const route = useRoute();
const activeIndex = computed(() => NAV_ITEMS.findIndex((item) => item.to === route.path));

/** Each nav row is 44px tall with a 4px gap. */
const ROW = 48;
</script>

<template>
  <aside
    data-testid="shell.sidebar"
    :data-collapsed="collapsed || undefined"
    :class="
      cn(
        'glass relative z-20 flex h-full min-h-0 flex-col rounded-none border-y-0 border-l-0 border-r-ui border-line/60',
        'px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-[max(0.75rem,env(safe-area-inset-top))]',
      )
    "
  >
    <div :class="cn('flex items-center gap-2.5 px-2 pb-4', collapsed && 'justify-center px-0')">
      <span
        aria-hidden="true"
        class="grid h-8 w-8 shrink-0 place-items-center rounded-ctl bg-brand text-primary-fg shadow-glow-primary"
      >
        <i class="pi pi-bolt text-sm" />
      </span>
      <span :class="cn('font-display text-base font-bold tracking-display text-fg', collapsed && 'sr-only')">
        BigWhales
      </span>
    </div>

    <nav aria-label="Primary" class="relative flex-1">
      <span
        v-if="activeIndex >= 0"
        data-part="active-indicator"
        aria-hidden="true"
        class="pointer-events-none absolute left-0 top-0 h-11 w-0.5 rounded-full bg-primary transition-transform duration-base ease-standard"
        :style="{ transform: `translateY(${activeIndex * ROW}px)` }"
      />
      <ul role="list" class="flex flex-col gap-1">
        <li v-for="item in NAV_ITEMS" :key="item.name">
          <NavItem :item="item" :collapsed="collapsed" />
        </li>
      </ul>
    </nav>

    <div :class="cn('flex items-center gap-1 pt-3', collapsed ? 'flex-col' : 'justify-between px-1')">
      <UiIconButton
        data-testid="shell.sidebar.settings"
        size="md"
        :label="'Appearance settings'"
        @click="emit('openSettings')"
      >
        <i class="pi pi-sliders-h" aria-hidden="true" />
      </UiIconButton>
      <UiIconButton
        data-testid="shell.sidebar-toggle"
        size="md"
        :label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'"
        :aria-expanded="!collapsed"
        @click="emit('update:collapsed', !props.collapsed)"
      >
        <i :class="collapsed ? 'pi pi-angle-double-right' : 'pi pi-angle-double-left'" aria-hidden="true" />
      </UiIconButton>
    </div>
  </aside>
</template>
