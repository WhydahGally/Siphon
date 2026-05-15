<script setup>
const props = defineProps({
  warnings: { type: Array, required: true },
  playlistId: { type: String, required: true },
})

const emit = defineEmits(['dismiss', 'clear-all'])

async function dismissWarning(warning) {
  const vid = warning.video_id
  if (!vid) return
  const res = await fetch(`/playlists/${props.playlistId}/warnings/${vid}`, { method: 'DELETE' })
  if (res.ok) emit('dismiss', vid)
}

async function clearAll() {
  const res = await fetch(`/playlists/${props.playlistId}/warnings`, { method: 'DELETE' })
  if (res.ok) emit('clear-all')
}
</script>

<template>
  <div class="warnings-panel">
    <div v-if="warnings.length === 0" class="panel-empty">
      No warnings.
    </div>

    <template v-else>
      <div class="panel-header">
        <span class="header-label">⚠ Warnings ({{ warnings.length }})</span>
        <button class="btn-clear-all" @click="clearAll">Clear All</button>
      </div>

      <div class="scroller">
        <div class="scroll-inner">
          <div v-for="(w, i) in warnings" :key="w.video_id || i" class="warning-item">
            <button class="btn-dismiss" title="Dismiss" @click="dismissWarning(w)">✕</button>
            <span class="warning-message">{{ w.message }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.warnings-panel {
  max-height: 70vh;
  overflow: hidden;
  border-top: 1px solid var(--border);
  background: var(--bg);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  border-bottom: 1px solid var(--border);
}

.header-label {
  font-size: 13px;
  font-weight: 600;
  color: #e6a700;
}

.btn-clear-all {
  font-size: 12px;
  padding: 3px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.btn-clear-all:hover {
  color: var(--text);
  border-color: var(--text-muted);
}

.panel-empty {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.scroller {
  max-height: calc(70vh - 40px);
  overflow-y: auto;
}

.scroll-inner {
  min-width: 100%;
}

.warning-item {
  display: flex;
  align-items: center;
  padding: 0 20px;
  height: 40px;
  box-sizing: border-box;
  gap: 10px;
}

.btn-dismiss {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, background 0.15s;
}
.btn-dismiss:hover {
  color: #e05252;
  background: rgba(224, 82, 82, 0.1);
}

.warning-message {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
