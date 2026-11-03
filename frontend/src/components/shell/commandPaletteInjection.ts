import type { InjectionKey } from "vue";

/**
 * Opens the shell's command palette. Provided by `AppShell.vue`, so a full-screen view that covers the topbar
 * (the liquidity theater mode) can still offer search. Injected with a null default: outside the shell there is
 * no palette.
 */
export const OPEN_COMMAND_PALETTE_INJECTION_KEY: InjectionKey<() => void> = Symbol("openCommandPalette");
