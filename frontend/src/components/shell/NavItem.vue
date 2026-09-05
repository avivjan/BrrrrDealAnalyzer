<script setup lang="ts">
/**
 * One primary-navigation link. A `RouterLink` in `custom` mode so the anchor
 * is ours: it carries the hook, `aria-current="page"` when exact-active, and
 * keeps its label in the DOM (visually hidden) when the sidebar is collapsed,
 * so a collapsed sidebar is still a labelled one.
 */
import { RouterLink } from "vue-router";

import { cn } from "../../design/cn";
import type { NavItemData } from "./nav";

withDefaults(
  defineProps<{
    item: NavItemData;
    collapsed?: boolean;
    /** Bottom-nav layout: icon over a tiny label, centred. */
    stacked?: boolean;
  }>(),
  { collapsed: false, stacked: false },
);
</script>

<template>
  <RouterLink :to="item.to" custom v-slot="{ href, navigate, isExactActive }">
    <a
      :href="href"
      :data-testid="`shell.nav.${item.name}`"
      :aria-current="isExactActive ? 'page' : undefined"
      :title="collapsed ? item.label : undefined"
      :class="
        cn(
          'group relative flex items-center rounded-ctl text-sm font-medium outline-none transition-[color,background-color,box-shadow] duration-fast ease-standard',
          'focus-visible:ring-2 focus-visible:ring-ring',
          stacked
            ? 'min-h-11 min-w-[3.25rem] flex-col justify-center gap-0.5 px-1 py-1 text-[10px]'
            : 'min-h-11 gap-3 px-3',
          collapsed && !stacked && 'justify-center px-0',
          isExactActive
            ? 'bg-primary/12 text-fg shadow-glow-primary'
            : 'text-fg-muted hover:bg-fg/6 hover:text-fg',
        )
      "
      @click="navigate"
    >
      <i
        :class="cn(item.icon, stacked ? 'text-base' : 'w-5 text-center text-base', isExactActive ? 'text-primary' : 'text-fg-muted group-hover:text-fg')"
        aria-hidden="true"
      />
      <span :class="cn('truncate', collapsed && !stacked && 'sr-only')">{{ item.label }}</span>
    </a>
  </RouterLink>
</template>
