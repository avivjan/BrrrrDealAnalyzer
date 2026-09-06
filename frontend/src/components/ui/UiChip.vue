<script setup lang="ts">
/**
 * A compact labelled pill: a filter, a tag, a count, a resource link.
 *
 * Unlike `UiBadge` (a status, never interactive) a chip may be a link — pass
 * `href` and it renders an `<a>` with a 44 px touch floor. The label is the
 * slot's; the chip hard-codes no word.
 */
import { computed, useAttrs } from "vue";

import { cn } from "../../design/cn";

type Tone = "neutral" | "primary" | "accent" | "positive" | "negative" | "warning";

const props = withDefaults(
  defineProps<{
    tone?: Tone;
    size?: "sm" | "md";
    href?: string;
    as?: string;
    /** A primeicons class rendered before the label. Decorative. */
    icon?: string;
  }>(),
  { tone: "neutral", size: "sm", href: undefined, as: undefined, icon: undefined },
);

defineOptions({ inheritAttrs: false });

const TONES: Record<Tone, string> = {
  neutral: "border-line bg-surface-2 text-fg-muted",
  primary: "border-primary/40 bg-primary/10 text-primary",
  accent: "border-accent/40 bg-accent/10 text-accent",
  positive: "border-positive/40 bg-positive/10 text-positive",
  negative: "border-negative/40 bg-negative/10 text-negative",
  warning: "border-warning/40 bg-warning/10 text-warning",
};

const SIZES = { sm: "min-h-7 px-2.5 text-xs", md: "min-h-8 px-3 text-sm" } as const;

const tag = computed(() => props.as ?? (props.href ? "a" : "span"));
const interactive = computed(() => tag.value === "a" || tag.value === "button");

const attrs = useAttrs();

function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

const rootClass = computed(() =>
  cn(
    "inline-flex items-center gap-1.5 rounded-full border-ui font-medium leading-none",
    "transition-[color,background-color,border-color,box-shadow] duration-fast ease-standard",
    TONES[props.tone],
    SIZES[props.size],
    interactive.value &&
      "touch:min-h-11 cursor-pointer no-underline hover:shadow-1 hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    attrs.class as string,
  ),
);
</script>

<template>
  <component :is="tag" data-ui="chip" :href="href" :class="rootClass" v-bind="passthrough()">
    <i v-if="icon" :class="cn(icon, 'text-[0.85em]')" aria-hidden="true" />
    <slot />
  </component>
</template>
