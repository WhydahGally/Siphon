<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import PlaylistRow from './PlaylistRow.vue'

const playlists = ref([])
const itemCache = ref({})         // { [playlist_id]: items[] }
const itemsLoading = ref({})      // { [playlist_id]: bool }
const expandedId = ref(null)

let syncEventsSource = null
const rowRefs = ref({})           // { [playlist_id]: PlaylistRow component ref }

// ── Fetch all playlists ──────────────────────────────────────────────────────

async function loadPlaylists() {
  try {
    const res = await fetch('/playlists')
    if (res.ok) {
      playlists.value = await res.json()
    }
  } catch {
    // daemon not reachable
  }
}

// ── Refresh a single playlist row (called after sync_done) ──────────────────

async function refreshPlaylist(playlistId) {
  try {
    const res = await fetch(`/playlists/${playlistId}`)
    if (res.ok) {
      const updated = await res.json()
      const idx = playlists.value.findIndex(p => p.id === playlistId)
      if (idx !== -1) {
        playlists.value[idx] = { ...playlists.value[idx], ...updated }
      }
    }
  } catch {}
}

// ── SSE: subscribe to sync lifecycle events ──────────────────────────────────

function connectSyncEvents() {
  syncEventsSource = new EventSource('/playlists/sync-events')

  syncEventsSource.onmessage = async (e) => {
    try {
      const { event, playlist_id, new_items } = JSON.parse(e.data)
      if (event === 'sync_started') {
        const p = playlists.value.find(pl => pl.id === playlist_id)
        if (p) p.is_syncing = true
      } else if (event === 'sync_info') {
        const rowRef = rowRefs.value[playlist_id]
        if (rowRef) rowRef.setSyncInfo(new_items)
      } else if (event === 'sync_done') {
        const p = playlists.value.find(pl => pl.id === playlist_id)
        if (p) p.is_syncing = false
        // Clear row's local syncing state
        const rowRef = rowRefs.value[playlist_id]
        if (rowRef) rowRef.clearSyncing()
        // Refresh row metadata (last_synced_at, item_count)
        refreshPlaylist(playlist_id)
        // If the panel is open, replace cache in place so the list updates live.
        // If closed, delete so the next expand fetches fresh.
        if (expandedId.value === playlist_id) {
          try {
            const res = await fetch(`/playlists/${playlist_id}/items`)
            if (res.ok) itemCache.value[playlist_id] = await res.json()
          } catch {}
        } else {
          delete itemCache.value[playlist_id]
        }
      }
    } catch {}
  }

  syncEventsSource.onerror = () => {
    // On error, close and re-fetch playlists to sync is_syncing truth
    syncEventsSource.close()
    loadPlaylists()
  }
}

// ── Accordion expand logic ───────────────────────────────────────────────────

async function handleExpand(playlistId) {
  expandedId.value = playlistId
  if (!itemCache.value[playlistId]) {
    itemsLoading.value[playlistId] = true
    try {
      const res = await fetch(`/playlists/${playlistId}/items`)
      if (res.ok) {
        itemCache.value[playlistId] = await res.json()
      }
    } catch {}
    itemsLoading.value[playlistId] = false
  }
}

function handleCollapse() {
  expandedId.value = null
}

// ── Delete ───────────────────────────────────────────────────────────────────

function handleDeleted(playlistId) {
  playlists.value = playlists.value.filter(p => p.id !== playlistId)
  delete itemCache.value[playlistId]
  if (expandedId.value === playlistId) expandedId.value = null
}

// ── Lifecycle ────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadPlaylists()
  connectSyncEvents()
})

onUnmounted(() => {
  if (syncEventsSource) syncEventsSource.close()
})
</script>

<template>
  <div class="library">
    <h2 class="section-title">Your library</h2>

    <div v-if="playlists.length === 0" class="empty-state">
      No playlists yet. Add one from the Dashboard.
    </div>

    <div v-else class="playlist-list">
      <PlaylistRow
        v-for="playlist in playlists"
        :key="playlist.id"
        :ref="el => { if (el) rowRefs[playlist.id] = el }"
        :playlist="playlist"
        :expanded="expandedId === playlist.id"
        :items="itemCache[playlist.id] || []"
        :items-loading="!!itemsLoading[playlist.id]"
        @expand="handleExpand"
        @collapse="handleCollapse"
        @deleted="handleDeleted"
      />
    </div>
  </div>
</template>

<style scoped>
.library {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 32px 0;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.empty-state {
  color: var(--text-muted);
  font-size: 14px;
  text-align: center;
  padding: 48px 0;
}

.playlist-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>

