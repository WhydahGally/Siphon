<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
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
const syncInfo = computed(() => props.playlist.sync_info ?? null)

// Interval inline edit
const editingInterval = ref(false)
const intervalInput = ref('')
const currentIntervalSecs = ref(props.playlist.check_interval_secs)
const intervalEditRef = ref(null)
const mobileIntervalEditRef = ref(null)
let _intervalClickOutside = null

const intervalDisplay = computed(() => secsToHuman(currentIntervalSecs.value))

function openIntervalEdit() {
  intervalInput.value = secsToDdhhmmss(currentIntervalSecs.value)
  editingInterval.value = true
  nextTick(() => {
    // Focus whichever edit group is currently visible
    const activeRef = mobileIntervalEditRef.value ?? intervalEditRef.value
    activeRef?.querySelector('input')?.focus()
    _intervalClickOutside = (e) => {
      const inDesktop = intervalEditRef.value?.contains(e.target)
      const inMobile = mobileIntervalEditRef.value?.contains(e.target)
      if (!inDesktop && !inMobile) {
        cancelIntervalEdit()
      }
    }
    document.addEventListener('mousedown', _intervalClickOutside)
  })
}

function _removeIntervalListener() {
  if (_intervalClickOutside) {
    document.removeEventListener('mousedown', _intervalClickOutside)
    _intervalClickOutside = null
  }
}

async function saveInterval() {
  _removeIntervalListener()
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
  _removeIntervalListener()
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

function formatSyncedDate(iso) {
  if (!iso) return 'never synced'
  const diffMs = new Date() - new Date(iso)
  if (diffMs < 60000) return 'less than a minute ago'
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}h ago`
  return formatDate(iso)
}

defineExpose({ clearSyncing })

// Marquee: scroll playlist name if it overflows the column
const titleContainerRef = ref(null)
const titleTextRef = ref(null)
const shouldMarquee = ref(false)
const marqueeDuration = ref('8s')
const marqueeShift = ref('0px')

onMounted(() => {
  const container = titleContainerRef.value
  const text = titleTextRef.value
  if (container && text && text.scrollWidth > container.clientWidth) {
    shouldMarquee.value = true
    const dist = text.scrollWidth - container.clientWidth
    marqueeDuration.value = Math.max(4, Math.round(dist / 60)) + 's'
    marqueeShift.value = `-${dist}px`
  }
})
</script>

<template>
  <div class="playlist-row" :class="{ expanded }">

    <!-- ══ MOBILE HEADER (≤640px only) ══════════════════════════════════════ -->
    <div class="mobile-header">
      <div class="mobile-title-row">
        <span class="playlist-name mobile-name">{{ playlist.name }}</span>
        <div class="mobile-header-actions">
          <button
            class="btn-sync-icon"
            :style="{ visibility: syncing ? 'hidden' : 'visible' }"
            title="Sync now"
            @click="triggerSync"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </button>
          <div class="mobile-delete">
            <ConfirmButton label="Delete" @confirm="handleDelete">
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                <path d="M10 11v6M14 11v6"/>
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
              </svg>
            </ConfirmButton>
          </div>
        </div>
      </div>
      <div v-if="syncing" class="sync-indicator mobile-sync-indicator">
        <span class="spinner" />
        <span class="syncing-label">
          {{ syncInfo === null ? 'Syncing…' : (syncInfo === 0 ? 'No new items found' : `${syncInfo} new item${syncInfo === 1 ? '' : 's'} found`) }}
        </span>
      </div>
      <div v-else class="mobile-meta">
        <span class="meta-item">{{ playlist.item_count }} items</span>
        <span class="meta-sep">·</span>
        <span class="meta-item">Added {{ formatSyncedDate(playlist.added_at) }}</span>
        <span class="meta-sep">·</span>
        <span class="meta-item">{{ playlist.last_synced_at ? `Synced ${formatSyncedDate(playlist.last_synced_at)}` : 'Never synced' }}</span>
      </div>
      <div class="mobile-controls">
        <label class="toggle-label">
          <span class="toggle-switch">
            <input type="checkbox" :checked="autoRename" @change="toggleAutoRename" />
            <span class="slider" />
          </span>
          <span>Auto rename</span>
        </label>
        <label class="toggle-label">
          <span class="toggle-switch">
            <input type="checkbox" :checked="watched" @change="toggleWatched" />
            <span class="slider" />
          </span>
          <span class="autosync-text">Auto sync
            <template v-if="watched">&mdash;
              <span v-if="!editingInterval" class="interval-display" @click.prevent.stop="openIntervalEdit">
                {{ intervalDisplay }}<svg class="pencil-icon" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              </span>
              <span v-else ref="mobileIntervalEditRef" class="interval-edit-group" @click.stop>
                <input v-model="intervalInput" class="interval-input" placeholder="DD:HH:MM:SS" @keydown.enter.prevent="saveInterval" @keydown.escape="cancelIntervalEdit" />
                <button class="btn-save-interval" title="Save" @mousedown.stop @click="saveInterval">
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
              </span>
            </template>
          </span>
        </label>
      </div>
    </div>
    <!-- ══ END MOBILE HEADER ═══════════════════════════════════════════════ -->

    <div class="row-body">

      <!-- Left: expand strip -->
      <button
        class="expand-strip"
        :class="{ 'is-expanded': expanded }"
        title="View the items in this playlist"
        @click="toggleExpand"
      >
        <span class="chevron">›</span>
      </button>

      <!-- col-2: title + sync button -->
      <div class="row-left">
        <div ref="titleContainerRef" class="row-title-line">
          <span
            ref="titleTextRef"
            class="playlist-name"
            :class="{ marquee: shouldMarquee }"
            :style="shouldMarquee ? { '--marquee-duration': marqueeDuration, '--marquee-shift': marqueeShift } : {}"
          >{{ playlist.name }}</span>
        </div>
        <button class="btn-sync" :style="{ visibility: syncing ? 'hidden' : 'visible' }" @click="triggerSync">Sync now</button>
      </div>

      <!-- col-3: meta + controls -->
      <div class="row-right">
        <div class="row-meta-slot">
          <div class="row-meta-line" :style="{ visibility: syncing ? 'hidden' : 'visible' }">
            <span class="meta-item">{{ playlist.item_count }} items</span>
            <span class="meta-sep">·</span>
            <span class="meta-item">Added {{ formatSyncedDate(playlist.added_at) }}</span>
            <span class="meta-sep">·</span>
            <span class="meta-item">
              {{ playlist.last_synced_at ? `Synced ${formatSyncedDate(playlist.last_synced_at)}` : 'Never synced' }}
            </span>
          </div>
          <div v-if="syncing" class="sync-indicator">
            <span class="spinner" />
            <span class="syncing-label">
              {{ syncInfo === null ? 'Syncing…' : (syncInfo === 0 ? 'No new items found' : `${syncInfo} new item${syncInfo === 1 ? '' : 's'} found`) }}
            </span>
          </div>
        </div>
        <div class="controls-group">
          <label class="toggle-label">
            <span class="toggle-switch">
              <input type="checkbox" :checked="autoRename" @change="toggleAutoRename" />
              <span class="slider" />
            </span>
            <span>Auto rename</span>
          </label>

          <label class="toggle-label">
            <span class="toggle-switch">
              <input type="checkbox" :checked="watched" @change="toggleWatched" />
              <span class="slider" />
            </span>
            <span class="autosync-text">Auto sync &mdash;
              <span
                v-if="!editingInterval"
                class="interval-display"
                title="Click to edit sync interval"
                @click.prevent.stop="openIntervalEdit"
              >{{ intervalDisplay }}<svg class="pencil-icon" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></span>
              <span v-else ref="intervalEditRef" class="interval-edit-group" @click.stop>
                <input
                  v-model="intervalInput"
                  class="interval-input"
                  placeholder="DD:HH:MM:SS"
                  @keydown.enter.prevent="saveInterval"
                  @keydown.escape="cancelIntervalEdit"
                />
                <button class="btn-save-interval" title="Save" @mousedown.stop @click="saveInterval">
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
              </span>
            </span>
          </label>
        </div>
      </div>

      <!-- Right: delete strip -->
      <div class="delete-strip">
        <ConfirmButton label="Delete" @confirm="handleDelete">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
        </ConfirmButton>
      </div>

    </div>

    <!-- ══ MOBILE EXPAND BAR (≤640px only) ══════════════════════════════ -->
    <button
      class="mobile-expand-bar"
      :class="{ 'is-expanded': expanded }"
      @click="toggleExpand"
    >
      <span class="chevron">›</span>
    </button>
    <!-- ══ END MOBILE EXPAND BAR ═════════════════════════════════════════ -->

    <!-- Items panel — full width below the three-column body -->
    <PlaylistItemsPanel
      v-if="expanded"
      :items="items"
      :loading="itemsLoading"
      :playlist-id="playlist.id"
    />
  </div>
</template>

<style scoped>
/* ── Outer card ──────────────────────────────────────────────── */
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

/* ── Four-column body ───────────────────────────────────────── */
.row-body {
  display: grid;
  grid-template-columns: 52px 250px 1fr 76px;
  align-items: stretch;
}

/* ── Left: expand strip ──────────────────────────────────────── */
.expand-strip {
  width: 52px;
  flex-shrink: 0;
  background: transparent;
  border: none;
  border-right: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}

.expand-strip:hover {
  background: rgba(124, 106, 247, 0.07);
}

.chevron {
  font-size: 22px;
  line-height: 1;
  color: var(--text-muted);
  display: inline-block;
  transform: rotate(0deg);
  transition: transform 0.22s ease, color 0.2s, text-shadow 0.2s;
  /* text-shadow transition starts immediately so glow is visible before tooltip */
  user-select: none;
}

.expand-strip:hover .chevron {
  color: var(--accent);
  text-shadow: 0 0 10px var(--accent), 0 0 20px rgba(124, 106, 247, 0.4);
}

.expand-strip.is-expanded .chevron {
  transform: rotate(90deg);
  color: var(--accent);
}

/* ── col-2 + col-3 ──────────────────────────────────────────── */
.row-left {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 20px;
  padding: 12px 16px 12px 14px;
  min-width: 0;
}

.row-right {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px 12px 24px;
  min-width: 0;
}

.row-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  width: 100%;
}

.row-meta-slot {
  position: relative;
}

.row-meta-slot .sync-indicator {
  position: absolute;
  top: 0;
  left: 0;
}

.row-meta-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.playlist-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  display: inline-block;
}

.playlist-name.marquee {
  animation: marquee-scroll var(--marquee-duration, 8s) linear infinite;
}

@keyframes marquee-scroll {
  0%   { transform: translateX(0); }
  40%  { transform: translateX(0); }
  90%  { transform: translateX(var(--marquee-shift, 0px)); }
  100% { transform: translateX(0); }
}

.sync-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.syncing-label {
  font-size: 12px;
  color: var(--accent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.meta-item {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.meta-sep {
  font-size: 20px;
  color: var(--text-muted);
  opacity: 0.5;
  flex-shrink: 0;
  line-height: 1;
}

.controls-group {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  flex: 1;
  margin-top: 5px;
}

.btn-sync {
  width: 96px;
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

.interval-display {
  cursor: pointer;
  border-bottom: 1px dashed var(--border);
  padding-bottom: 1px;
  transition: color 0.15s, border-color 0.15s;
}

.interval-display:hover {
  color: var(--text);
  border-bottom-color: var(--text-muted);
}

.pencil-icon {
  vertical-align: middle;
  margin-left: 3px;
  opacity: 0.5;
}

.interval-edit-group {
  display: inline-flex;
  align-items: center;
  gap: 5px;
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

.btn-save-interval {
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  color: #fff;
  padding: 4px 7px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s, border-color 0.15s;
}

.btn-save-interval:hover {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}

/* ── Right: delete strip ─────────────────────────────────────── */
.delete-strip {
  width: 76px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 10px;
}

/* ── Spinner ─────────────────────────────────────────────────── */
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

/* ── Mobile-only elements (hidden on desktop) ───────────────── */
.mobile-header { display: none; }
.mobile-expand-bar { display: none; }

/* ── Mobile layout (≤640px) ─────────────────────────────────── */
@media (max-width: 640px) {
  /* Hide desktop-only columns */
  .expand-strip { display: none; }
  .row-left { display: none; }
  .row-right { display: none; }
  .delete-strip { display: none; }
  .row-body { display: none; }

  /* Show mobile header */
  .mobile-header {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 14px 8px;
  }

  .mobile-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .mobile-name {
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
  }

  .mobile-header-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .btn-sync-icon {
    background: none;
    border: 1px solid var(--accent);
    color: var(--accent);
    border-radius: var(--radius-sm);
    padding: 5px 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
  }
  .btn-sync-icon:hover { background: rgba(124, 106, 247, 0.1); }

  .mobile-delete {
    display: flex;
    align-items: center;
  }

  .mobile-sync-indicator {
    padding-top: 0;
  }

  .mobile-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .mobile-controls {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 4px 0 4px;
  }

  /* Full-width expand bar at bottom */
  .mobile-expand-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    background: transparent;
    border: none;
    border-top: 1px solid var(--border);
    padding: 6px 0;
    cursor: pointer;
    transition: background 0.2s;
  }
  .mobile-expand-bar:hover { background: rgba(124, 106, 247, 0.07); }
  .mobile-expand-bar .chevron {
    font-size: 20px;
    color: var(--text-muted);
    transition: transform 0.22s ease, color 0.2s;
  }
  .mobile-expand-bar:hover .chevron { color: var(--accent); }
  .mobile-expand-bar.is-expanded .chevron {
    transform: rotate(90deg);
    color: var(--accent);
  }

  .interval-input { width: 90px; }
}
</style>
