<script setup>
import { useToast } from '../composables/useToast.js'

const { toasts, dismiss } = useToast()
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast"
          :class="toast.type"
        >
          <span class="toast-msg">{{ toast.message }}</span>
          <button class="toast-close" @click="dismiss(toast.id)">✕</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 9999;
  pointer-events: none;
  align-items: center;
}

.toast {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 16px;
  border-radius: 7px;
  font-size: 13px;
  min-width: 280px;
  max-width: 460px;
  pointer-events: all;
  border: 1px solid transparent;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.toast.error {
  background: #2a1515;
  border-color: rgba(224, 85, 85, 0.35);
  color: #f0a0a0;
}

.toast.info {
  background: #161a2a;
  border-color: rgba(124, 106, 247, 0.35);
  color: #b0aaf7;
}

.toast-msg {
  flex: 1;
  line-height: 1.4;
}

.toast-close {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.55;
  font-size: 11px;
  padding: 2px 4px;
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity 0.15s;
}

.toast-close:hover {
  opacity: 1;
}

/* Transition */
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
