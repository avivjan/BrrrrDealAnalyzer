<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

/**
 * Hover-/tap-to-reveal breakdown popover.
 *
 * Renders a small info icon next to its slot content. On desktop (fine
 * pointer) the popover follows mouseenter/mouseleave; on touch devices a tap
 * toggles it. The popover floats above siblings via a teleport-free fixed
 * position to avoid being clipped by overflow:hidden cards.
 */
const props = defineProps<{
  /** Tooltip header (e.g. "Cash Flow"). */
  title: string;
  /** Formula/explanation body. If empty, the trigger is hidden entirely. */
  formula?: string | null;
  /** Tailwind colour for the icon. */
  iconColor?: string;
}>();

const open = ref(false);
const triggerEl = ref<HTMLElement | null>(null);
const popoverEl = ref<HTMLElement | null>(null);

const popStyle = ref<{ top: string; left: string; maxWidth: string }>({
  top: "0px",
  left: "0px",
  maxWidth: "320px",
});

const hasFormula = computed(() => !!(props.formula && props.formula.trim()));

const iconClass = computed(
  () => props.iconColor || "text-gray-400 hover:text-blue-500",
);

/**
 * Position the popover above the icon, clamped to the viewport so it never
 * spills off the right edge or the top of the page (when near the header).
 * Uses `position: fixed` so we don't get clipped by parent overflow rules.
 */
function reposition() {
  if (!triggerEl.value) return;
  const rect = triggerEl.value.getBoundingClientRect();
  const margin = 8;
  const desiredWidth = Math.min(320, window.innerWidth - margin * 2);
  let left = rect.left + rect.width / 2 - desiredWidth / 2;
  left = Math.max(margin, Math.min(left, window.innerWidth - desiredWidth - margin));
  // We render above by default; if there's not enough room, fall back below.
  const popHeight = popoverEl.value?.offsetHeight ?? 80;
  let top = rect.top - popHeight - 10;
  if (top < margin) {
    top = rect.bottom + 10;
  }
  popStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    maxWidth: `${desiredWidth}px`,
  };
}

function show() {
  if (!hasFormula.value) return;
  open.value = true;
  // Wait for popover to mount so we can measure it.
  requestAnimationFrame(reposition);
}

function hide() {
  open.value = false;
}

function toggle() {
  if (open.value) hide();
  else show();
}

function onDocClick(ev: MouseEvent) {
  if (!open.value) return;
  const target = ev.target as Node | null;
  if (!target) return;
  if (
    triggerEl.value && triggerEl.value.contains(target)
  ) {
    return;
  }
  if (popoverEl.value && popoverEl.value.contains(target)) {
    return;
  }
  hide();
}

onMounted(() => {
  document.addEventListener("click", onDocClick, true);
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick, true);
  window.removeEventListener("scroll", hide, true);
  window.removeEventListener("resize", hide);
});
</script>

<template>
  <span class="inline-flex items-center gap-1">
    <slot />
    <button
      v-if="hasFormula"
      ref="triggerEl"
      type="button"
      class="inline-flex items-center justify-center w-4 h-4 rounded-full transition-colors focus:outline-none focus:ring-1 focus:ring-blue-400"
      :class="iconClass"
      :aria-label="`${title} breakdown`"
      :title="`${title} breakdown`"
      @mouseenter="show"
      @mouseleave="hide"
      @focus="show"
      @blur="hide"
      @click.stop="toggle"
    >
      <i class="pi pi-info-circle text-[11px]"></i>
    </button>
    <Teleport to="body">
      <div
        v-if="open && hasFormula"
        ref="popoverEl"
        class="fixed z-[1000] px-3 py-2 rounded-lg shadow-xl bg-gray-900 text-white text-xs leading-snug pointer-events-auto"
        :style="popStyle"
        role="tooltip"
      >
        <div class="font-semibold text-blue-200 mb-1 uppercase tracking-wide text-[10px]">
          {{ title }}
        </div>
        <div class="font-mono whitespace-normal break-words text-[11px]">
          {{ formula }}
        </div>
      </div>
    </Teleport>
  </span>
</template>
