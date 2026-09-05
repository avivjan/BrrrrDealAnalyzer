/**
 * Global registration of the presentational primitives.
 *
 * Phase 3 restyles the views in place under a script freeze: a view template
 * may write `<UiButton>` but its `<script setup>` may not gain an import line.
 * The primitives are therefore registered on the app itself — here, once — and
 * the same map is installed on `config.global.components` by the Vitest setup
 * file, so a mounted view resolves them without any local registration.
 *
 * Only the presentational primitives belong here. Anything that owns state or
 * talks to a store stays a normal, explicitly imported component.
 */
import type { App } from "vue";

import {
  UiBadge,
  UiButton,
  UiCard,
  UiEmptyState,
  UiField,
  UiIconButton,
  UiModalPanel,
  UiSaveStatus,
  UiSectionHeader,
  UiSkeleton,
  UiStatTile,
  UiStepper,
  UiTabs,
} from "./index";

/**
 * The globally registered primitives, keyed by the tag templates use.
 *
 * `src/components.d.ts` mirrors these names into `vue`'s `GlobalComponents`
 * so `vue-tsc` type-checks the props a template passes them.
 */
export const UI_COMPONENTS = {
  UiButton,
  UiIconButton,
  UiCard,
  UiBadge,
  UiStatTile,
  UiField,
  UiModalPanel,
  UiSectionHeader,
  UiEmptyState,
  UiSkeleton,
  UiSaveStatus,
  UiTabs,
  UiStepper,
} as const;

/** Register every primitive on `app`, so templates need no import. */
export function registerUiPrimitives(app: App): void {
  for (const [name, component] of Object.entries(UI_COMPONENTS)) {
    app.component(name, component);
  }
}
