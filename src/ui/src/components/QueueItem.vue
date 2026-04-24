<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  jobId: { type: String, required: true },
  playlistId: { type: String, default: null },
  autoRename: { type: Boolean, default: false },
})

const editing = ref(false)
const editInput = ref('')
let _clickOutside = null

function openEdit() {
  editing.value = true
  editInput.value = props.item.renamed_to || props.item.yt_title
  nextTick(() => {
    const el = document.querySelector(`.queue-item.done .rename-input[data-vid="${props.item.video_id}"]`)
    el?.focus()
    el?.select()
    _clickOutside = (e) => {
      const wrapper = document.querySelector(`.rename-edit-wrapper[data-vid="${props.item.video_id}"]`)
      if (wrapper && !wrapper.contains(e.target)) cancelEdit()
    }
    document.addEventListener('mousedown', _clickOutside)
  })
}

async function saveEdit() {
  _removeListener()
  const newName = editInput.value.trim()
  if (!newName) { cancelEdit(); return }
  if (newName === (props.item.renamed_to || props.item.yt_title)) { cancelEdit(); return }

  const url = `/jobs/${props.jobId}/items/${props.item.video_id}/rename`

  try {
    const resp = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName }),
    })
    if (!resp.ok) { cancelEdit(); return }
    const updated = await resp.json()
    props.item.renamed_to = updated.renamed_to
    props.item.rename_tier = updated.rename_tier
  } catch { /* ignore */ }
  editing.value = false
}

function cancelEdit() {
  _removeListener()
  editing.value = false
}

function _removeListener() {
  if (_clickOutside) {
    document.removeEventListener('mousedown', _clickOutside)
    _clickOutside = null
  }
}
</script>

<template>
  <div class="queue-item" :class="item.state">
    <span class="state-icon">
      <span v-if="item.state === 'downloading'" class="spinner" />
      <span v-else-if="item.state === 'done'" class="check">✓</span>
      <span v-else-if="item.state === 'failed'" class="cross">✕</span>
      <span v-else-if="item.state === 'cancelled'" class="dash">–</span>
      <span v-else class="dot" />
    </span>

    <div class="item-info">
      <!-- Edit mode (done items only) -->
      <template v-if="item.state === 'done' && editing">
        <span class="item-title">
          <span class="original-title">{{ item.yt_title }}</span>
          <span class="arrow"> → </span>
          <span class="rename-edit-wrapper" :data-vid="item.video_id">
            <input
              v-model="editInput"
              class="rename-input"
              :data-vid="item.video_id"
              @keydown.enter.prevent="saveEdit"
              @keydown.escape="cancelEdit"
            />
            <button class="btn-save" title="Save" @mousedown.stop @click="saveEdit">
              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </button>
          </span>
        </span>
      </template>
      <!-- Display mode -->
      <template v-else>
        <span v-if="item.state === 'done' && item.renamed_to && (autoRename || item.rename_tier === 'manual')" class="item-title">
          <span class="original-title">{{ item.yt_title }}</span>
          <span class="arrow"> → </span>
          <span class="renamed-title">{{ item.renamed_to }}</span>
          <span v-if="(autoRename || item.rename_tier === 'manual') && item.rename_tier" class="tier-badge">{{ item.rename_tier }}</span>
          <svg class="pencil-icon" @click.stop="openEdit" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </span>
        <span v-else-if="item.state === 'done'" class="item-title">
          {{ item.yt_title }}
          <svg class="pencil-icon" @click.stop="openEdit" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </span>
        <span v-else class="item-title">{{ item.yt_title }}</span>
      </template>

      <span v-if="item.state === 'failed' && item.error" class="item-error">{{ item.error }}</span>
    </div>
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

.queue-item.cancelled {
  opacity: 0.5;
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

.dash {
  color: var(--text-muted);
  font-size: 16px;
  font-weight: 300;
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
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.item-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  min-height: 26px;
  font-size: 14px;
  color: var(--text);
  white-space: nowrap;
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
.queue-item.done:hover .pencil-icon { opacity: 0.5; }
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

.item-error {
  font-size: 12px;
  color: var(--error);
  white-space: nowrap;
}
</style>
