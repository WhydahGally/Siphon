<script setup>
import { ref, computed } from 'vue'
import ConfirmButton from './ConfirmButton.vue'
import PlaylistItemsPanel from './PlaylistItemsPanel.vue'
import { secsToHuman, ddhhmmssToSecs, secsToDdhhmmss } from '../utils/interval.js'

const props = defineProps({
  playlist: { type: Object, required: true },
  expanded: { type: Boolean, default: false },
  items: { type: Array, default: () => [] },
  itemsLoading: { type: Boolean, default: false },
})
const emit = defineEmits(['expand', 'collapse', 'deleted'])

// local copies of mutable state
const autoRename = ref(props.playlist.auto_rename)
const watched = ref(props.playlist.watched)
const syncing = ref(props.playlist.is_syncing)

// Interval inline edit
const editingInterval = ref(false)
const intervalInput = ref('')
const currentIntervalSecs = ref(props.playlist.check_interval_secs)

const intervalDisplay = computed(() => secsToHuman(currentIntervalSecs.value))

function openIntervalEdit() {
  intervalInput.value = secsToDdhhmmss(currentIntervalSecs.value)
  editingInterval.value = true
}

async function saveInterval() {
  const secs = ddhhmmssToSecs(intervalInput.value)
  editingInterval.value = false
  if (secs === null) return
  try {
    await fetch(`/playlists/${props.playlist.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ check_interval_secs: secs }),
    })
    currentIntervalSecs.value = secs
  } catch {}
}

function cancelIntervalEdit() {
  editingInterval.value = false
}

// Sync now
async function triggerSync() {
  if (syncing.value) return
  syncing.value = true
  try {
    await fetch(`/playlists/${props.playlist.id}/sync`, { method: 'POST' })
  } catch {
    syncing.value = false
  }
}

// Clear syncing state from parent (called when sync_done received)
function clearSyncing() {
  syncing.value = false
}

// Toggles
async function toggleAutoRename() {
  const next = !autoRename.value
  autoRename.value = next
  try {
    await fetch(`/playlists/${props.playlist.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_rename: next }),
    })
  } catch {
    autoRename.value = !next // revert on error
  }
}

async function toggleWatched() {
  const next = !watched.value
  watched.value = next
  try {
    await fetch(`/playlists/${props.playlist.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watched: next }),
    })
  } catch {
    watched.value = !next
  }
}

// Delete
async function handleDelete() {
  try {
    const res = await fetch(`/playlists/${props.playlist.id}`, { method: 'DELETE' })
    if (res.ok || res.status === 204) {
      emit('deleted', props.playlist.id)
    }
  } catch {}
}

// Expand / collapse
function toggleExpand() {
  if (props.expanded) {
    emit('collapse', props.playlist.id)
  } else {
    emit('expand', props.playlist.id)
  }
}

// Date formatting
function formatDate(iso) {
  if (!iso) return 'never synced'
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffDays === 0) return 'today'
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 30) return `${diffDays}d ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
  return `${Math.floor(diffDays / 365)}y ago`
}

defineExpose({ clearSyncing })
</script>

<template>
  <div class="playlist-row" :class="{ expanded }">
    <!-- Main row content -->
    <div class="row-header">
      <!-- Left: name + meta -->
      <div class="row-left">
        <div class="row-title-line">
          <span class="playlist-name">{{ playlist.name }}</span>
          <span v-if="syncing" class="sync-indicator">
            <span class="spinner" />
            <span class="syncing-label">Syncing…</span>
          </span>
        </div>
        <div class="row-meta">
          <span class="meta-item">{{ playlist.item_count }} items</span>
          <span class="meta-sep">·</span>
          <span class="meta-item">Added {{ formatDate(playlist.added_at) }}</span>
          <span class="meta-sep">·</span>
          <span class="meta-item">
            {{ playlist.last_synced_at ? `Synced ${formatDate(playlist.last_synced_at)}` : 'Never synced' }}
          </span>
        </div>
      </div>

      <!-- Right: delete -->
      <div class="row-right">
        <ConfirmButton label="Delete" danger-label="Delete" @confirm="handleDelete" />
      </div>
    </div>

    <!-- Controls row -->
    <div class="row-controls">
      <!-- Sync now -->
      <button v-if="!syncing" class="btn-sync" @click="triggerSync">Sync now</button>
      <div v-else class="sync-placeholder" />

      <div class="controls-group">
        <!-- Auto rename toggle -->
        <label class="toggle-label">
          <span class="toggle-switch">
            <input type="checkbox" :checked="autoRename" @change="toggleAutoRename" />
            <span class="slider" />
          </span>
          <span>Auto rename</span>
        </label>

        <!-- Auto sync toggle -->
        <label class="toggle-label">
          <span class="toggle-switch">
            <input type="checkbox" :checked="watched" @change="toggleWatched" />
            <span class="slider" />
          </span>
          <span>Auto sync</span>
        </label>

        <!-- Interval inline edit -->
        <div class="interval-wrapper">
          <span
            v-if="!editingInterval"
            class="interval-display"
            :title="'Click to edit sync interval'"
            @click="openIntervalEdit"
          >{{ intervalDisplay }}</span>
          <input
            v-else
            v-model="intervalInput"
            class="interval-input"
            placeholder="DD:HH:MM:SS"
            autofocus
            @keydown.enter="saveInterval"
            @keydown.escape="cancelIntervalEdit"
            @blur="saveInterval"
          />
        </div>

        <!-- Expand button -->
        <button class="btn-expand" @click="toggleExpand">
          {{ expanded ? '▲ Items' : '▶ Items' }}
        </button>
      </div>
    </div>

    <!-- Items panel (accordion) -->
    <PlaylistItemsPanel
      v-if="expanded"
      :items="items"
      :loading="itemsLoading"
    />
  </div>
</template>

<style scoped>
.playlist-row {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: border-color 0.15s;
}

.playlist-row.expanded {
  border-color: var(--accent);
}

.row-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px 0;
}

.row-left {
  flex: 1;
  min-width: 0;
}

.row-title-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.playlist-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sync-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.syncing-label {
  font-size: 12px;
  color: var(--accent);
}

.row-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
  flex-wrap: wrap;
}

.meta-item {
  font-size: 12px;
  color: var(--text-muted);
}

.meta-sep {
  font-size: 12px;
  color: var(--border);
}

.row-right {
  flex-shrink: 0;
}

.row-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px 14px;
  flex-wrap: wrap;
}

.controls-group {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  flex: 1;
}

.btn-sync {
  background: none;
  border: 1px solid var(--accent);
  color: var(--accent);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}

.btn-sync:hover {
  background: rgba(124, 106, 247, 0.1);
}

.sync-placeholder {
  width: 80px;
  flex-shrink: 0;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  color: var(--text-muted);
}

.toggle-switch {
  position: relative;
  width: 32px;
  height: 18px;
  flex-shrink: 0;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}

.slider {
  position: absolute;
  inset: 0;
  border-radius: 18px;
  background: var(--border);
  transition: background 0.2s;
}

.slider::before {
  content: '';
  position: absolute;
  height: 12px;
  width: 12px;
  left: 3px;
  top: 3px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: transform 0.2s, background 0.2s;
}

.toggle-switch input:checked + .slider {
  background: var(--accent);
}

.toggle-switch input:checked + .slider::before {
  transform: translateX(14px);
  background: #fff;
}

.interval-wrapper {
  display: flex;
  align-items: center;
}

.interval-display {
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 1px dashed var(--border);
  padding-bottom: 1px;
  transition: color 0.15s, border-color 0.15s;
}

.interval-display:hover {
  color: var(--text);
  border-bottom-color: var(--text-muted);
}

.interval-input {
  width: 110px;
  background: var(--surface-2);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  padding: 4px 7px;
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.btn-expand {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
  margin-left: auto;
}

.btn-expand:hover {
  color: var(--text);
  border-color: var(--text-muted);
}

/* Spinner */
.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(124, 106, 247, 0.3);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
