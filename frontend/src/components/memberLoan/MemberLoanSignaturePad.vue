<script setup lang="ts">
/**
 * Draw a signature with a finger, a pen or the mouse. Emits the drawing as a
 * PNG data URL after every stroke (null once cleared), sized for the server's
 * limit (60 KB; a 600 × 200 canvas of strokes is far below it).
 *
 * Pointer events cover touch, pen and mouse alike; `touch-action: none` stops
 * the page from scrolling while the member signs. The canvas is drawn at the
 * device's pixel ratio so the line stays sharp, then exported at a fixed size.
 */
import { onBeforeUnmount, onMounted, ref } from "vue";

const emit = defineEmits<{ change: [pngDataUrl: string | null] }>();

const EXPORT_WIDTH_PIXELS = 600;
const EXPORT_HEIGHT_PIXELS = 200;

const canvas = ref<HTMLCanvasElement | null>(null);
const hasInk = ref(false);
let drawing = false;
let lastPoint: { x: number; y: number } | null = null;
let resizeObserver: ResizeObserver | null = null;

function context(): CanvasRenderingContext2D | null {
  return canvas.value?.getContext("2d") ?? null;
}

function sizeCanvasToItsBox() {
  const element = canvas.value;
  if (!element) return;
  const ratio = window.devicePixelRatio || 1;
  const box = element.getBoundingClientRect();
  const width = Math.max(1, Math.round(box.width * ratio));
  const height = Math.max(1, Math.round(box.height * ratio));
  if (width === element.width && height === element.height && hasInk.value) return; // nothing to redraw for
  element.width = width;
  element.height = height;
  const ctx = context();
  if (ctx) {
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.lineWidth = 2.4;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#0b1f3a";
  }
  clear();
}

function pointOf(event: PointerEvent) {
  const box = canvas.value!.getBoundingClientRect();
  return { x: event.clientX - box.left, y: event.clientY - box.top };
}

function start(event: PointerEvent) {
  if (!canvas.value) return;
  canvas.value.setPointerCapture?.(event.pointerId);
  drawing = true;
  lastPoint = pointOf(event);
  const ctx = context();
  if (ctx) {
    ctx.beginPath();
    ctx.arc(lastPoint.x, lastPoint.y, 1.1, 0, Math.PI * 2);
    ctx.fillStyle = "#0b1f3a";
    ctx.fill();
  }
  hasInk.value = true;
}

function move(event: PointerEvent) {
  if (!drawing || !lastPoint) return;
  const point = pointOf(event);
  const ctx = context();
  if (ctx) {
    ctx.beginPath();
    ctx.moveTo(lastPoint.x, lastPoint.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
  }
  lastPoint = point;
}

function end() {
  if (!drawing) return;
  drawing = false;
  lastPoint = null;
  emit("change", exportPng());
}

function exportPng(): string | null {
  if (!canvas.value || !hasInk.value) return null;
  const exported = document.createElement("canvas");
  exported.width = EXPORT_WIDTH_PIXELS;
  exported.height = EXPORT_HEIGHT_PIXELS;
  exported.getContext("2d")?.drawImage(canvas.value, 0, 0, EXPORT_WIDTH_PIXELS, EXPORT_HEIGHT_PIXELS);
  return exported.toDataURL("image/png");
}

function clear() {
  const element = canvas.value;
  const ctx = context();
  if (element && ctx) ctx.clearRect(0, 0, element.width, element.height);
  hasInk.value = false;
  emit("change", null);
}

onMounted(() => {
  sizeCanvasToItsBox();
  if (typeof ResizeObserver !== "undefined" && canvas.value) {
    resizeObserver = new ResizeObserver(() => sizeCanvasToItsBox());
    resizeObserver.observe(canvas.value);
  }
});
onBeforeUnmount(() => resizeObserver?.disconnect());

defineExpose({ clear });
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="relative rounded-ctl border-2 border-dashed border-line bg-page">
      <canvas
        ref="canvas"
        class="block h-40 w-full cursor-crosshair touch-none select-none sm:h-48"
        role="img"
        :aria-label="hasInk ? 'Your drawn signature' : 'Signature pad: draw your signature here'"
        data-testid="member-loan.signature-pad"
        @pointerdown.prevent="start"
        @pointermove.prevent="move"
        @pointerup="end"
        @pointerleave="end"
        @pointercancel="end"
      />
      <span v-if="!hasInk" class="pointer-events-none absolute inset-x-0 bottom-3 text-center text-xs text-fg-muted">
        Sign here with your finger or mouse
      </span>
      <span class="pointer-events-none absolute inset-x-6 bottom-9 border-b border-line" aria-hidden="true" />
    </div>
    <div class="flex justify-end">
      <UiButton variant="ghost" size="sm" :disabled="!hasInk" data-testid="member-loan.signature-clear" @click="clear">
        <i class="pi pi-refresh" aria-hidden="true" /> Clear and draw again
      </UiButton>
    </div>
  </div>
</template>
