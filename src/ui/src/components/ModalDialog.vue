<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="onOverlayClick" @keydown.escape="$emit('close')">
      <div
        class="modal-content"
        :style="{ maxWidth }"
        role="dialog"
        aria-modal="true"
        ref="modalRef"
        tabindex="-1"
        @keydown.tab="trapFocus"
      >
        <button class="modal-close" @click="$emit('close')" aria-label="Close">&times;</button>
        <div v-if="$slots.header" class="modal-header">
          <slot name="header" />
        </div>
        <div class="modal-body">
          <slot name="body" />
        </div>
        <div v-if="$slots.actions" class="modal-actions">
          <slot name="actions" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  show: { type: Boolean, required: true },
  maxWidth: { type: String, default: '520px' },
  closeOnOverlay: { type: Boolean, default: true },
})

const emit = defineEmits(['close'])
const modalRef = ref(null)

function onOverlayClick() {
  if (props.closeOnOverlay) emit('close')
}

function trapFocus(e) {
  if (!modalRef.value) return
  const focusable = modalRef.value.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  )
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

watch(() => props.show, (val) => {
  if (val) {
    nextTick(() => {
      modalRef.value?.focus()
    })
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-content {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  width: 90%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
  outline: none;
}

.modal-close {
  position: absolute;
  top: 12px;
  right: 14px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
  padding: 4px;
  transition: color 0.15s;
}

.modal-close:hover {
  color: var(--text);
}

.modal-header {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  padding-right: 28px;
}

.modal-body {
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.6;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* Mobile responsive */
@media (max-width: 600px) {
  .modal-content {
    width: calc(100% - 32px);
    max-width: 100% !important;
    margin: 0 16px;
  }

  .modal-actions {
    flex-direction: column;
  }

  .modal-actions :deep(button) {
    width: 100%;
  }
}
</style>
