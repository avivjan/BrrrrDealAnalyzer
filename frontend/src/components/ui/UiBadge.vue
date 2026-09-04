<script setup lang="ts">
/**
 * A status pill: a tinted ground, token ink, and whatever the slot says.
 *
 * The label is always the caller's — the badge hard-codes no word, so the copy
 * gate keeps reading the string from the template that owns it. `dealType` is
 * the one place the component contributes anything, and it contributes an icon
 * (never a word), because BRRRR and FLIP are told apart by colour today and
 * colour alone is not a distinction a colour-blind user can make.
 *
 * `dealType` also picks the tone, and deliberately overrides an explicit
 * `tone`: a FLIP badge tinted "negative" would be a lie about the strategy,
 * and silently letting the two disagree is worse than ignoring one of them.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Tone = "neutral" | "primary" | "positive" | "negative" | "warning" | "info";
type Size = "sm" | "md";
type DealType = "BRRRR" | "FLIP";

const props = withDefaults(
  defineProps<{
    tone?: Tone;
    size?: Size;
    /** Sets the icon and the tone together; overrides `tone` when both are given. */
    dealType?: DealType;
  }>(),
  { tone: "neutral", size: "sm", dealType: undefined },
);

defineOptions({ inheritAttrs: false });

// No transition utilities here on purpose: a badge has no hover, focus or
// active state to travel between, so a transition would only ever animate a
// tone prop changing under it — a jump the reader should see immediately.
const BASE = "inline-flex items-center gap-1 rounded-full text-xs font-medium leading-none";

/**
 * A 10% wash of the tone with the tone itself as ink. `info` is the exception:
 * the palette has no semantic "info" colour, and `chart-4` is a categorical
 * hue chosen to sit next to five others on a canvas, not to be read as text at
 * 12px — so the wash is sky and the ink stays `fg`.
 */
const TONES: Record<Tone, string> = {
  neutral: "bg-surface-muted text-fg-muted",
  primary: "bg-primary/10 text-primary",
  positive: "bg-positive/10 text-positive",
  negative: "bg-negative/10 text-negative",
  warning: "bg-warning/10 text-warning",
  info: "bg-chart-4/15 text-fg ring-1 ring-inset ring-chart-4/40",
};

const SIZES: Record<Size, string> = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-1 text-sm",
};

const DEAL_TYPES: Record<DealType, { icon: string; tone: Tone }> = {
  BRRRR: { icon: "pi pi-home", tone: "primary" },
  FLIP: { icon: "pi pi-dollar", tone: "warning" },
};

const dealType = computed(() => (props.dealType ? DEAL_TYPES[props.dealType] : null));

const attrs = useAttrs();

/**
 * Everything except `class`, which `rootClass` folds through `cn()` instead.
 *
 * A plain function rather than a `computed`, and it matters: the object
 * `useAttrs()` hands back tracks a read of a *key*, so spreading it while it
 * holds no keys registers no dependency at all. A computed would cache that
 * first empty result for the life of the component and quietly swallow every
 * attribute the parent adds later. Recomputing per render costs one object.
 */
function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() =>
  cn(BASE, TONES[dealType.value?.tone ?? props.tone], SIZES[props.size], attrs.class as string),
);
</script>

<template>
  <span data-ui="badge" :class="rootClass" v-bind="passthrough()">
    <i v-if="dealType" :class="dealType.icon" aria-hidden="true" />
    <slot />
  </span>
</template>
