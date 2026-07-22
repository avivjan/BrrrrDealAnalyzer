<script setup lang="ts">
defineProps<{
  text: string
}>()
</script>

<template>
  <span class="info-tip" tabindex="0">
    <i class="pi pi-info-circle"></i>
    <span class="info-tip-bubble" role="tooltip">{{ text }}</span>
  </span>
</template>

<style scoped>
.info-tip {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.35);
  cursor: help;
  outline: none;
}

.info-tip i {
  font-size: 0.72rem;
}

.info-tip:hover,
.info-tip:focus-visible {
  color: rgba(255, 255, 255, 0.65);
}

.info-tip-bubble {
  position: absolute;
  bottom: calc(100% + 0.45rem);
  left: 50%;
  transform: translateX(-50%);
  width: max-content;
  max-width: 220px;
  padding: 0.45rem 0.6rem;
  border-radius: 0.5rem;
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.68rem;
  line-height: 1.35;
  font-weight: 500;
  text-align: left;
  box-shadow: 0 12px 30px -10px rgba(0, 0, 0, 0.65);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity 0.15s ease, visibility 0.15s ease;
  z-index: 20;
}

.info-tip:hover .info-tip-bubble,
.info-tip:focus-visible .info-tip-bubble {
  opacity: 1;
  visibility: visible;
}
</style>
