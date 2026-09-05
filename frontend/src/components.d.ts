/**
 * Ambient typing for the globally registered primitives and motion wrappers.
 *
 * `registerUiPrimitives` (see `src/components/ui/register.ts`) and
 * `registerMotion` (see `src/motion/index.ts`) register these on the app, so no
 * template imports them; without this augmentation `vue-tsc` would see every
 * `<UiButton>` as an unknown element and check nothing. The lists must stay in
 * step — a name here that is not registered type-checks a tag that fails to
 * resolve at runtime.
 *
 * `export {}` makes this file a module, so `declare module "vue"` augments the
 * real `vue` types instead of declaring a new ambient module that replaces them.
 */
export {};

declare module "vue" {
  export interface GlobalComponents {
    UiButton: typeof import("./components/ui/UiButton.vue")["default"];
    UiIconButton: typeof import("./components/ui/UiIconButton.vue")["default"];
    UiCard: typeof import("./components/ui/UiCard.vue")["default"];
    UiBadge: typeof import("./components/ui/UiBadge.vue")["default"];
    UiStatTile: typeof import("./components/ui/UiStatTile.vue")["default"];
    UiField: typeof import("./components/ui/UiField.vue")["default"];
    UiModalPanel: typeof import("./components/ui/UiModalPanel.vue")["default"];
    UiSectionHeader: typeof import("./components/ui/UiSectionHeader.vue")["default"];
    UiEmptyState: typeof import("./components/ui/UiEmptyState.vue")["default"];
    UiSkeleton: typeof import("./components/ui/UiSkeleton.vue")["default"];
    UiSaveStatus: typeof import("./components/ui/UiSaveStatus.vue")["default"];
    UiTabs: typeof import("./components/ui/UiTabs.vue")["default"];
    UiStepper: typeof import("./components/ui/UiStepper.vue")["default"];

    // Motion (src/motion), registered by `registerMotion`.
    UiTransition: typeof import("./motion/UiTransition.vue")["default"];
    UiTransitionGroup: typeof import("./motion/UiTransitionGroup.vue")["default"];
  }
}
