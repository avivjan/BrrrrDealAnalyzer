<script setup lang="ts">
/**
 * The Look section of Settings → Appearance: four radio cards, each showing
 * its own look. Radio semantics — the group has one tab stop (the checked
 * card), the arrow keys move the choice, Space/Enter check the focused one.
 * The check mark is an icon as well as a colour, so the chosen card reads
 * without hue.
 */
import { computed, ref } from "vue";

import { cn } from "../../design/cn";
import { LOOKS, type LookId } from "../../design/looks";
import type { ResolvedTheme } from "../../design/theme";
import LookPreview from "./LookPreview.vue";

const props = withDefaults(defineProps<{ modelValue: LookId; mode?: ResolvedTheme }>(), { mode: "dark" });
const emit = defineEmits<{ "update:modelValue": [value: LookId] }>();

const cards = ref<HTMLElement[]>([]);
const index = computed(() => LOOKS.findIndex((look) => look.id === props.modelValue));

function choose(id: LookId, focus = false) {
  emit("update:modelValue", id);
  if (focus) cards.value[LOOKS.findIndex((look) => look.id === id)]?.focus();
}

function move(delta: number) {
  const from = index.value < 0 ? 0 : index.value;
  const next = (from + delta + LOOKS.length) % LOOKS.length;
  choose(LOOKS[next]!.id, true);
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case "ArrowRight":
    case "ArrowDown":
      event.preventDefault();
      move(1);
      break;
    case "ArrowLeft":
    case "ArrowUp":
      event.preventDefault();
      move(-1);
      break;
    default:
  }
}
</script>

<template>
  <div role="radiogroup" aria-label="Look" data-testid="shell.look-picker" class="grid grid-cols-2 gap-3" @keydown="onKeydown">
    <button
      v-for="look in LOOKS"
      :key="look.id"
      ref="cards"
      type="button"
      role="radio"
      :aria-checked="look.id === modelValue"
      :tabindex="look.id === modelValue || (index < 0 && look === LOOKS[0]) ? 0 : -1"
      :data-testid="`shell.look.${look.id}`"
      :class="
        cn(
          'group flex min-h-11 flex-col gap-2 rounded-card border-ui p-2 text-left transition-[border-color,box-shadow,transform] duration-fast ease-standard',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface',
          look.id === modelValue
            ? 'border-primary bg-primary/6 shadow-glow-primary'
            : 'border-line bg-surface hover:border-fg/25 hover:-translate-y-px',
        )
      "
      @click="choose(look.id)"
    >
      <LookPreview :look-id="look.id" :mode="mode" />
      <span class="flex items-start justify-between gap-2 px-0.5">
        <span class="min-w-0">
          <span class="block text-sm font-semibold text-fg">{{ look.name }}</span>
          <span class="block text-xs leading-snug text-fg-muted">{{ look.tagline }}</span>
        </span>
        <i
          :class="cn('mt-0.5 shrink-0 text-sm', look.id === modelValue ? 'pi pi-check-circle text-primary' : 'pi pi-circle text-fg-muted/50')"
          aria-hidden="true"
        />
      </span>
    </button>
  </div>
</template>
