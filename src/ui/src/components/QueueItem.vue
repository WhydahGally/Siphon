<script setup>
defineProps({
  item: { type: Object, required: true },
  jobId: { type: String, required: true },
})
const emit = defineEmits(['retry'])
</script>

<template>
  <div class="queue-item" :class="item.state">
    <span class="state-icon">
      <span v-if="item.state === 'downloading'" class="spinner" />
      <span v-else-if="item.state === 'done'" class="check">✓</span>
      <span v-else-if="item.state === 'failed'" class="cross">✕</span>
      <span v-else class="dot" />
    </span>

    <div class="item-info">
      <span v-if="item.state === 'done' && item.renamed_to" class="item-title">
        <span class="original-title">{{ item.yt_title }}</span>
        <span class="arrow"> → </span>
        <span class="renamed-title">{{ item.renamed_to }}</span>
      </span>
      <span v-else class="item-title">{{ item.yt_title }}</span>

      <span v-if="item.state === 'failed' && item.error" class="item-error">{{ item.error }}</span>
    </div>

    <button
      v-if="item.state === 'failed'"
      class="btn-retry"
      @click="emit('retry', jobId)"
    >
      Retry
    </button>
  </div>
</template>

<style scoped>
.queue-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  transition: background 0.15s;
}

.queue-item.failed {
  background: var(--error-bg);
}

.queue-item.downloading {
  background: rgba(124, 106, 247, 0.06);
}

.state-icon {
  width: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(124, 106, 247, 0.3);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.check {
  color: var(--success);
  font-size: 14px;
  font-weight: 700;
}

.cross {
  color: var(--error);
  font-size: 14px;
  font-weight: 700;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--border);
  display: inline-block;
}

.item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.item-title {
  font-size: 14px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.original-title {
  color: var(--text-muted);
}

.arrow {
  color: var(--text-muted);
}

.renamed-title {
  color: var(--text);
  font-weight: 500;
}

.item-error {
  font-size: 12px;
  color: var(--error);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-retry {
  flex-shrink: 0;
  background: none;
  border: 1px solid var(--error);
  color: var(--error);
  border-radius: var(--radius-sm);
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.15s;
}

.btn-retry:hover {
  background: var(--error-bg);
}
</style>
