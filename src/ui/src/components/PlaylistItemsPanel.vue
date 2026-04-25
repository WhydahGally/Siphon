<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  playlistId: { type: String, default: null },
})

const TIER_LABELS = {
  metadata: 'Metadata',
  musicbrainz: 'MusicBrainz',
  title: 'Title',
  manual: 'Manual',
}

function tierLabel(tier) {
  return TIER_LABELS[tier] ?? tier
}

const editingVideoId = ref(null)
const editInput = ref('')
let _clickOutside = null

function openEdit(item) {
  editingVideoId.value = item.video_id
  editInput.value = item.renamed_to || item.title
  nextTick(() => {
    const el = document.querySelector('.rename-input')
    el?.focus()
    el?.select()
    _clickOutside = (e) => {
      const wrapper = document.querySelector('.rename-edit-wrapper')
      if (wrapper && !wrapper.contains(e.target)) cancelEdit()
    }
    document.addEventListener('mousedown', _clickOutside)
  })
}

async function saveEdit(item) {
  _removeListener()
  const newName = editInput.value.trim()
  if (!newName) { cancelEdit(); return }
  if (newName === (item.renamed_to || item.title)) { cancelEdit(); return }
  try {
    const resp = await fetch(`/playlists/${props.playlistId}/items/${item.video_id}/rename`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName }),
    })
    if (!resp.ok) { cancelEdit(); return }
    const updated = await resp.json()
    item.renamed_to = updated.renamed_to
    item.rename_tier = updated.rename_tier
  } catch { /* ignore */ }
  editingVideoId.value = null
}

function cancelEdit() {
  _removeListener()
  editingVideoId.value = null
}

function _removeListener() {
  if (_clickOutside) {
    document.removeEventListener('mousedown', _clickOutside)
    _clickOutside = null
  }
}
</script>

<template>
  <div class="items-panel">
    <div v-if="loading" class="panel-loading">
      <span class="spinner" />
      <span class="loading-text">Loading items…</span>
    </div>

    <div v-else-if="items.length === 0" class="panel-empty">
      No items downloaded yet.
    </div>

    <div v-else class="scroller">
      <div class="scroll-inner">
        <div v-for="item in items" :key="item.video_id" class="panel-item">
          <div class="item-titles">
            <!-- Edit mode -->
            <template v-if="editingVideoId === item.video_id">
              <span class="item-title">
                <span class="original">{{ item.title }}</span>
                <span class="arrow"> → </span>
                <span class="rename-edit-wrapper">
                  <input
                    v-model="editInput"
                    class="rename-input"
                    @keydown.enter.prevent="saveEdit(item)"
                    @keydown.escape="cancelEdit"
                  />
                  <button class="btn-save" title="Save" @mousedown.stop @click="saveEdit(item)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  </button>
                </span>
              </span>
            </template>
            <!-- Display mode -->
            <template v-else>
              <span v-if="item.renamed_to && item.rename_tier" class="item-title">
                <span class="original">{{ item.title }}</span>
                <span class="arrow"> → </span>
                <span class="renamed">{{ item.renamed_to }}</span>
                <span class="tier-badge">{{ tierLabel(item.rename_tier) }}</span>
                <svg class="pencil-icon" @click.stop="openEdit(item)" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </span>
              <span v-else class="item-title plain">
                {{ item.title }}
                <svg class="pencil-icon" @click.stop="openEdit(item)" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </span>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.items-panel {
  max-height: 70vh;
  overflow: hidden;
  border-top: 1px solid var(--border);
  background: var(--bg);
}

.scroller {
  max-height: 70vh;
  overflow-y: auto;
  overflow-x: auto;
}

.scroll-inner {
  width: max-content;
  min-width: 100%;
}

.panel-loading,
.panel-empty {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.panel-item {
  display: flex;
  align-items: center;
  padding: 0 20px;
  height: 40px;
  box-sizing: border-box;
}

.item-titles {
  flex: 1;
}

.item-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  min-height: 26px;
  font-size: 13px;
  white-space: nowrap;
}

.item-title.plain {
  color: var(--text);
}

.original {
  color: var(--text-muted);
}

.arrow {
  color: var(--text-muted);
}

.renamed {
  color: var(--text);
  font-weight: 500;
}

.tier-badge {
  display: inline-block;
  margin-left: 4px;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 6px;
  font-weight: 700;
  background: rgba(124, 106, 247, 0.15);
  color: var(--accent);
  vertical-align: super;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  line-height: 1;
}

.pencil-icon {
  opacity: 0;
  margin-left: 6px;
  cursor: pointer;
  color: var(--text-muted);
  vertical-align: middle;
  transition: opacity 0.15s;
}
.panel-item:hover .pencil-icon { opacity: 0.5; }
.pencil-icon:hover { opacity: 1 !important; color: var(--accent); }

.rename-edit-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  vertical-align: middle;
}

.rename-input {
  font-size: 13px;
  padding: 2px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg);
  color: var(--text);
  min-width: 180px;
}
.rename-input:focus { outline: none; border-color: var(--accent); }

.btn-save {
  padding: 4px 7px;
  border: 1px solid var(--accent);
  border-radius: 4px;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.btn-save:hover { opacity: 0.85; }

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(124, 106, 247, 0.3);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
