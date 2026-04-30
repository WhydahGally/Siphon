<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useToast } from '../composables/useToast.js'
import { ddhhmmssToSecs, secsToDdhhmmss, secsToHuman } from '../utils/interval.js'
import { useSettings } from '../composables/useSettings.js'

const emit = defineEmits(['job-created'])
const { showToast } = useToast()
const { autoRename: globalAutoRename, sponsorBlockEnabled: globalSponsorBlock, cookiesEnabled: globalCookiesEnabled, cookieFileSet, loaded: settingsLoaded } = useSettings()

const url = ref('')
const format = ref('mp3')
const quality = ref('best')
const autoRename = ref(globalAutoRename.value)
watch(globalAutoRename, (v) => { autoRename.value = v })
const sponsorBlock = ref(globalSponsorBlock.value)
watch(globalSponsorBlock, (v) => { sponsorBlock.value = v })
const useCookies = ref(globalCookiesEnabled.value)
watch(globalCookiesEnabled, (v) => { useCookies.value = v })
const autoSync = ref(true)
const interval = ref(86400)
const editingInterval = ref(false)
const intervalInput = ref('')
const intervalEditRef = ref(null)
const intervalDisplay = computed(() => secsToHuman(interval.value))
const loading = ref(false)

let _intervalClickOutside = null

function openIntervalEdit() {
  intervalInput.value = secsToDdhhmmss(interval.value)
  editingInterval.value = true
  nextTick(() => {
    intervalEditRef.value?.querySelector('input')?.focus()
    _intervalClickOutside = (e) => {
      if (intervalEditRef.value && !intervalEditRef.value.contains(e.target)) {
        cancelIntervalEdit()
      }
    }
    document.addEventListener('mousedown', _intervalClickOutside)
  })
}
function saveInterval() {
  _removeIntervalListener()
  const secs = ddhhmmssToSecs(intervalInput.value)
  editingInterval.value = false
  if (secs !== null) interval.value = secs
}
function cancelIntervalEdit() {
  _removeIntervalListener()
  editingInterval.value = false
}
function _removeIntervalListener() {
  if (_intervalClickOutside) {
    document.removeEventListener('mousedown', _intervalClickOutside)
    _intervalClickOutside = null
  }
}
const mbUserAgentMissing = ref(false)

const AUDIO_FORMATS = ['mp3', 'opus']
const VIDEO_FORMATS = ['mp4', 'mkv', 'webm']
const QUALITY_OPTIONS = ['best', '2160', '1080', '720', '480', '360']

const isAudio = computed(() => AUDIO_FORMATS.includes(format.value))

// Playlist URL detection — patterns fetched from the daemon (derived from yt-dlp
// extractor _VALID_URL regexes) so they stay in sync with yt-dlp automatically.
// Hardcoded regexes are used as a fallback if the fetch fails.
const _FALLBACK_PATH_RE = /\/(?:playlists?|albums?|channels?|sets|series|collections?|lists?|medialist|favlist|feed|users?)\//i
const _FALLBACK_PARAM_RE = /[?&](?:list|playlist|playlistid|album|channel|series|user)=/i
const _playlistPathRe = ref(_FALLBACK_PATH_RE)
const _playlistParamRe = ref(_FALLBACK_PARAM_RE)
const isPlaylist = computed(() =>
  _playlistPathRe.value.test(url.value) || _playlistParamRe.value.test(url.value)
)

onMounted(async () => {
  try {
    const res = await fetch('/settings/mb-user-agent')
    const data = await res.json()
    mbUserAgentMissing.value = !data.value
  } catch {
    // daemon not reachable yet — don't crash
  }
  try {
    const res = await fetch('/playlist-patterns')
    if (res.ok) {
      const { path_segments, query_params } = await res.json()
      if (path_segments?.length) {
        _playlistPathRe.value = new RegExp(`\\/(?:${path_segments.join('|')})\\/`, 'i')
      }
      if (query_params?.length) {
        _playlistParamRe.value = new RegExp(`[?&](?:${query_params.join('|')})=`, 'i')
      }
    }
  } catch {
    // fallback regexes remain active
  }
})

async function handleDownload() {
  if (!url.value.trim()) {
    showToast('Please enter a URL.')
    return
  }
  loading.value = true

  const body = {
    url: url.value.trim(),
    format: format.value,
    quality: isAudio.value ? 'best' : quality.value,
    auto_rename: autoRename.value,
    watched: isPlaylist.value ? autoSync.value : false,
    sponsorblock_enabled: sponsorBlock.value,
    use_cookies: useCookies.value,
  }
  if (isPlaylist.value && autoSync.value && interval.value) {
    body.check_interval_secs = Number(interval.value)
  }

  try {
    const res = await fetch('/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      showToast(data.detail || `Error ${res.status}`)
      return
    }
    const data = await res.json()
    if (data.existing_playlist) {
      showToast('Playlist already in library — syncing new videos.', 'info')
    }
    emit('job-created', data.job_id)
    url.value = ''
  } catch (e) {
    showToast('Could not reach the daemon. Is siphon running?')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="download-form">
    <h2 class="section-title">Download</h2>

    <!-- URL row -->
    <div class="url-row">
      <input
        v-model="url"
        class="url-input"
        placeholder="Playlist or video URL"
        :disabled="loading"
        @keydown.enter="handleDownload"
      />
      <button class="btn-primary" :disabled="loading" @click="handleDownload">
        <span v-if="loading" class="spinner-sm" />
        <span v-else>Download</span>
      </button>
    </div>

    <!-- Format + Quality row -->
    <div class="controls-row">
      <div class="control-group">
        <label class="control-label">Format</label>
        <select v-model="format" class="select" :disabled="loading">
          <optgroup label="Audio">
            <option v-for="f in AUDIO_FORMATS" :key="f" :value="f">{{ f }}</option>
          </optgroup>
          <optgroup label="Video">
            <option v-for="f in VIDEO_FORMATS" :key="f" :value="f">{{ f }}</option>
          </optgroup>
        </select>
      </div>

      <div class="control-group">
        <label class="control-label">Quality</label>
        <div
          class="quality-wrapper"
          :title="isAudio ? 'Audio is always downloaded at the best quality available' : ''"
        >
          <select
            v-model="quality"
            class="select"
            :disabled="isAudio || loading"
          >
            <option v-if="isAudio" value="best">best</option>
            <template v-else>
              <option v-for="q in QUALITY_OPTIONS" :key="q" :value="q">{{ q }}</option>
            </template>
          </select>
        </div>
      </div>
    </div>

    <!-- Toggles row -->
    <div class="toggles-row">
      <!-- Auto rename -->
      <label v-if="settingsLoaded" class="toggle-label">
        <span class="toggle-switch">
          <input v-model="autoRename" type="checkbox" :disabled="loading" />
          <span class="slider" />
        </span>
        <span>Auto rename</span>
        <span
          v-if="autoRename && mbUserAgentMissing"
          class="warn-icon"
          title="Configure mb-user-agent in settings."
        >⚠</span>
      </label>

      <!-- SponsorBlock -->
      <label v-if="settingsLoaded" class="toggle-label">
        <span class="toggle-switch">
          <input v-model="sponsorBlock" type="checkbox" :disabled="loading" />
          <span class="slider" />
        </span>
        <span>SponsorBlock</span>
      </label>

      <!-- Cookies -->
      <label v-if="settingsLoaded && cookieFileSet" class="toggle-label">
        <span class="toggle-switch">
          <input v-model="useCookies" type="checkbox" :disabled="loading" />
          <span class="slider" />
        </span>
        <span>Cookies</span>
      </label>

      <!-- Auto sync (playlist only) — interval is inline -->
      <label v-if="isPlaylist" class="toggle-label">
        <span class="toggle-switch">
          <input v-model="autoSync" type="checkbox" :disabled="loading" />
          <span class="slider" />
        </span>
        <span>Sync<template v-if="autoSync"> ·
          <span v-if="!editingInterval" class="interval-display" @click.stop.prevent="openIntervalEdit">
            {{ intervalDisplay }}
            <svg class="pencil-icon" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </span>
          <span v-else ref="intervalEditRef" class="interval-edit-group" @click.stop>
            <input
              v-model="intervalInput"
              class="interval-input"
              placeholder="DD:HH:MM:SS"
              title="Format - DD:HH:MM:SS"
              @keydown.enter.prevent="saveInterval"
              @keydown.escape="cancelIntervalEdit"
            />
            <button class="btn-save" title="Save" @mousedown.stop @click="saveInterval">
              <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </button>
          </span>
        </template></span>
      </label>
    </div>

  </section>
</template>

<style scoped>
.download-form {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}

.url-row {
  display: flex;
  gap: 10px;
}

.url-input {
  flex: 1;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 9px 12px;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s;
}

.url-input:focus {
  border-color: var(--accent);
}

.url-input:disabled {
  opacity: 0.5;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  padding: 9px 20px;
  font-weight: 600;
  white-space: nowrap;
  transition: background 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 100px;
  justify-content: center;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.controls-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.control-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.select {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  padding: 7px 10px;
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s;
  min-width: 110px;
}

.select:focus {
  border-color: var(--accent);
}

.select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.quality-wrapper {
  position: relative;
  display: inline-block;
}

.toggles-row {
  display: flex;
  align-items: center;
  gap: 30px;
  flex-wrap: wrap;
  min-height: 36px;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  color: var(--text-muted);
  min-height: 28px;
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

.warn-icon {
  color: var(--warning);
  font-size: 13px;
  cursor: help;
}

.interval-edit-group {
  display: inline-flex;
  align-items: center;
  gap: 5px;
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

.interval-input {
  width: 130px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 5px 10px;
  font-size: 13px;
  color: var(--text);
  outline: none;
}
.interval-input:focus { border-color: var(--accent); }

.btn-save {
  border-radius: var(--radius-sm);
  padding: 4px 7px;
  background: var(--accent);
  border: 1px solid var(--accent);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.btn-save:hover { background: var(--accent-hover); border-color: var(--accent-hover); }

.spinner-sm {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .download-form {
    padding: 16px;
  }

  .btn-primary {
    min-width: unset;
    padding: 9px 14px;
  }

  .controls-row {
    justify-content: space-between;
  }

  .toggles-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .interval-input {
    width: 110px;
  }
}
</style>
