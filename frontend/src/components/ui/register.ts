/**
 * Global registration of the presentational primitives.
 *
 * v1 restyled the views under a script freeze: a view template may write
 * `<UiButton>` but its `<script setup>` may not gain an import line. The
 * primitives are therefore registered on the app itself — here, once — and
 * the same map is installed on `config.global.components` by the Vitest setup
 * file, so a mounted view resolves them without any local registration. v2
 * keeps the convention: every primitive, old and new, is global.
 *
 * Only the presentational primitives belong here. Anything that owns state or
 * talks to a store stays a normal, explicitly imported component.
 */
import type { App } from "vue";

import {
  UiBadge,
  UiButton,
  UiCard,
  UiChip,
  UiCommandItem,
  UiDrawer,
  UiEmptyState,
  UiField,
  UiGlassPanel,
  UiIconButton,
  UiKpiCard,
  UiModalPanel,
  UiSaveStatus,
  UiSectionHeader,
  UiSegmented,
  UiSkeleton,
  UiStatTile,
  UiStepper,
  UiSurface,
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
  // UI v2. Registered = used by a template somewhere. `UiTooltip`,
  // `UiSparkline`, `UiProgressRing`, `UiTimelineRail` and `UiDataTable` are
  // built, tested and exported from `./index`, but no view has adopted them
  // yet; registering by value would put them in the bundle for nothing, so a
  // view that wants one imports it (and moves it here once it is global).
  UiSurface,
  UiGlassPanel,
  UiChip,
  UiKpiCard,
  UiDrawer,
  UiCommandItem,
  UiSegmented,
} as const;

/** Register every primitive on `app`, so templates need no import. */
export function registerUiPrimitives(app: App): void {
  for (const [name, component] of Object.entries(UI_COMPONENTS)) {
    app.component(name, component);
  }
}
