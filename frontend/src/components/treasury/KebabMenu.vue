<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const open = ref(false)
const root = ref<HTMLElement | null>(null)

function toggle() {
  open.value = !open.value
}

function close() {
  open.value = false
}

function onClickOutside(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) close()
}

onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))

defineExpose({ close })
</script>

<template>
  <div ref="root" class="kebab-menu">
    <button
      type="button"
      class="kebab-btn"
      aria-label="More actions"
      @click.stop="toggle"
    >
      <i class="pi pi-ellipsis-v"></i>
    </button>
    <transition name="menu-fade">
      <div v-if="open" class="kebab-panel" @click.stop>
        <slot :close="close" />
      </div>
    </transition>
  </div>
</template>

<style scoped>
.kebab-menu {
  position: relative;
}

.kebab-btn {
  width: 1.85rem;
  height: 1.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  color: rgba(255, 255, 255, 0.45);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.kebab-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

.kebab-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 0.4rem);
  min-width: 210px;
  background: #0f1420;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.8rem;
  box-shadow: 0 24px 48px -20px rgba(0, 0, 0, 0.65);
  padding: 0.4rem;
  z-index: 40;
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
