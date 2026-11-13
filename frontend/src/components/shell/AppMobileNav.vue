<script setup lang="ts">
/**
 * The phone's primary navigation: seven routes as icon-over-label tabs (Construction
 * accounts is reached from Liquidity, the Dashboard, the palette and `g` `c`),
 * fixed to the bottom edge, padded past the home indicator. Settings live in
 * the topbar gear, so the bar carries routes only.
 */
import { PHONE_BOTTOM_BAR_ITEMS } from "./nav";
import NavItem from "./NavItem.vue";
</script>

<template>
  <nav
    data-testid="shell.mobile-nav"
    aria-label="Primary"
    class="glass fixed inset-x-0 bottom-0 z-40 rounded-none border-x-0 border-b-0 border-t-ui border-line/60 px-1 pb-safe-b"
  >
    <ul role="list" class="grid grid-cols-7 gap-0.5 py-1">
      <li v-for="item in PHONE_BOTTOM_BAR_ITEMS" :key="item.name" class="min-w-0">
        <NavItem :item="item" stacked />
      </li>
    </ul>
  </nav>
</template>
