<script setup>
import { ref, onBeforeUnmount } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  dangerLabel: { type: String, default: 'Confirm' },
})
const emit = defineEmits(['confirm'])

const confirming = ref(false)
let timer = null

function startConfirm() {
  confirming.value = true
  timer = setTimeout(() => {
    confirming.value = false
    timer = null
  }, 5000)
}

function cancel() {
  clearTimeout(timer)
  timer = null
  confirming.value = false
}

function confirm() {
  clearTimeout(timer)
  timer = null
  confirming.value = false
  emit('confirm')
}

onBeforeUnmount(() => {
  clearTimeout(timer)
})
</script>

<template>
  <div class="confirm-button" :class="{ confirming }">
    <button v-if="!confirming" class="btn-default" @click="startConfirm">
      <slot>{{ label }}</slot>
    </button>
    <template v-else>
      <button class="btn-danger" @click="confirm">{{ dangerLabel }}</button>
      <button class="btn-cancel" @click="cancel">Cancel</button>
    </template>
  </div>
</template>

<style scoped>
.confirm-button {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  gap: 4px;
  min-height: 48px; /* pre-reserves split-state height: (22 + 4 + 22)px */
}

.btn-default {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 7px 14px;
  font-size: 15px;
  font-weight: 500;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-default:hover {
  color: var(--error);
  border-color: var(--error);
}

.btn-danger {
  background: var(--error);
  border: 1px solid var(--error);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1;
  font-weight: 600;
  transition: background 0.15s;
  white-space: nowrap;
}

.btn-danger:hover {
  background: #c94444;
  border-color: #c94444;
}

.btn-cancel {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1;
  font-weight: 500;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
}

.btn-cancel:hover {
  color: var(--text);
  border-color: var(--text-muted);
}
</style>
