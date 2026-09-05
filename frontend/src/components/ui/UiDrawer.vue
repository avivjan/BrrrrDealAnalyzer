<script setup lang="ts">
/**
 * A side panel over the page: Settings, filters, a mobile menu.
 *
 * Owns exactly the behaviour a drawer needs and nothing that belongs to its
 * content: it teleports to `<body>`, closes on Escape and on a click on the
 * scrim, moves focus into the panel on open and hands it back to the element
 * that had it on close. What the drawer says and does inside is the caller's;
 * the header slot is wrapped in an `h2` that names the dialog unless
 * `labelledby` points at one of the caller's own headings.
 *
 * The scrim is a plain `div` with `@click.self` — never transformed, so the
 * fixed positioning of the panel inside it holds on iOS — and the whole thing
 * sits in a `<UiTransition preset="drawer">`, which fades the scrim and slides
 * the panel in from its edge (`data-ui="modal-panel"` + `data-side` are what
 * that preset reads).
 */
import { computed, nextTick, onBeforeUnmount, ref, useAttrs, useId, watch } from "vue";

import { cn } from "../../design/cn";

const props = withDefaults(
  defineProps<{
    open: boolean;
    side?: "left" | "right";
    /** Id of a heading the caller renders; otherwise the header slot is the name. */
    labelledby?: string;
    /** Panel width class on `md+`; it is always full-width on phones. */
    size?: "sm" | "md" | "lg";
  }>(),
  { side: "right", labelledby: undefined, size: "md" },
);

const emit = defineEmits<{ close: [] }>();

defineOptions({ inheritAttrs: false });

const headingId = useId();
const panel = ref<HTMLElement | null>(null);
let restoreTo: HTMLElement | null = null;

const SIZES = { sm: "md:max-w-sm", md: "md:max-w-md", lg: "md:max-w-lg" } as const;

const labelledBy = computed(() => props.labelledby ?? headingId);

const attrs = useAttrs();

/** Everything except `class` (which goes on the panel) lands on the scrim root — the drawer's own element. */
function passthrough() {
  const rest: Record<string, unknown> = { ...attrs };
  delete rest.class;
  return rest;
}

/**
 * Escape closes the drawer from anywhere on the page while it is open.
 *
 * A native `document` listener rather than `@keydown` on the root, for two
 * reasons: focus may have left the panel (a screen reader's virtual cursor,
 * a stray click on the scrim), and Vue's per-event timestamp guard skips an
 * outer template handler when an inner one on the same path ran first under
 * a frozen clock — exactly the situation the e2e suite creates with its
 * paused fake clock. Registered only while open, removed on close and unmount.
 */
function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    event.stopPropagation();
    emit("close");
  }
}

function listen(open: boolean) {
  if (typeof document === "undefined") return;
  document.removeEventListener("keydown", onDocumentKeydown, true);
  if (open) document.addEventListener("keydown", onDocumentKeydown, true);
}

onBeforeUnmount(() => listen(false));

watch(
  () => props.open,
  async (open) => {
    if (typeof document === "undefined") return;
    listen(open);
    if (open) {
      restoreTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      await nextTick();
      // The first control in the *body* — not the header's Close button, which
      // precedes it in DOM order and would make every drawer open on "Close".
      const FOCUSABLE = 'input, select, textarea, button, [href], [tabindex]:not([tabindex="-1"])';
      const body = panel.value?.querySelector<HTMLElement>('[data-part="body"]');
      const first = body?.querySelector<HTMLElement>(FOCUSABLE) ?? null;
      (first ?? panel.value)?.focus();
    } else if (restoreTo) {
      restoreTo.focus();
      restoreTo = null;
    }
  },
  // `immediate`: a drawer mounted already open focuses its body too.
  { immediate: true },
);

</script>

<template>
  <Teleport to="body">
    <UiTransition preset="drawer">
      <div
        v-if="open"
        data-ui="drawer"
        class="fixed inset-0 z-50 flex bg-fg/40"
        :class="side === 'right' ? 'justify-end' : 'justify-start'"
        v-bind="passthrough()"
        @click.self="emit('close')"
      >
        <div
          ref="panel"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="labelledBy"
          data-ui="modal-panel"
          :data-side="side"
          tabindex="-1"
          :class="
            cn(
              'flex h-full w-full flex-col bg-surface text-fg shadow-4 outline-none',
              side === 'right' ? 'border-l border-line' : 'border-r border-line',
              SIZES[size],
              $attrs.class as string,
            )
          "
        >
          <div v-if="$slots.header" data-part="header" class="flex shrink-0 items-start justify-between gap-3 border-b border-line px-5 pb-4 pt-[max(1rem,env(safe-area-inset-top))]">
            <h2 v-if="!labelledby" :id="headingId" class="font-display text-lg font-semibold tracking-display">
              <slot name="header" />
            </h2>
            <div v-else class="font-display text-lg font-semibold tracking-display"><slot name="header" /></div>
            <UiIconButton label="Close" size="md" data-part="close" @click="emit('close')">
              <i class="pi pi-times" aria-hidden="true" />
            </UiIconButton>
          </div>
          <div data-part="body" class="custom-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4">
            <slot />
          </div>
          <div v-if="$slots.footer" data-part="footer" class="shrink-0 border-t border-line px-5 py-3 pb-safe-b text-sm text-fg-muted">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </UiTransition>
  </Teleport>
</template>
