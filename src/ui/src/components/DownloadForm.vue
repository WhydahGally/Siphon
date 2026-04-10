<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from '../composables/useToast.js'

const emit = defineEmits(['job-created'])
const { showToast } = useToast()

const url = ref('')
const format = ref('mp3')
const quality = ref('best')
const autoRename = ref(true)
const autoSync = ref(true)
const interval = ref(86400)
const loading = ref(false)
const mbUserAgentMissing = ref(false)

const AUDIO_FORMATS = ['mp3', 'opus']
const VIDEO_FORMATS = ['mp4', 'mkv', 'webm']
const QUALITY_OPTIONS = ['best', '2160', '1080', '720', '480', '360']

const isAudio = computed(() => AUDIO_FORMATS.includes(format.value))
const isPlaylist = computed(() => url.value.includes('list='))

onMounted(async () => {
  try {
    const res = await fetch('/settings/mb-user-agent')
    const data = await res.json()
    mbUserAgentMissing.value = !data.value
  } catch {
    // daemon not reachable yet — don't crash
  }
  try {
    const res = await fetch('/settings/auto-rename')
    const data = await res.json()
    if (data.value === 'false') autoRename.value = false
  } catch {
    // daemon not reachable — keep default true
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
    showToast('Could not reach the daemon. Is siphon watch running?')
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
        placeholder="YouTube playlist or video URL"
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
      <label class="toggle-label">
        <span class="toggle-switch">
          <input v-model="autoRename" type="checkbox" :disabled="loading" />
          <span class="slider" />
        </span>
        <span>Auto rename</span>
        <span
          v-if="autoRename && mbUserAgentMissing"
          class="warn-icon"
          title="MusicBrainz lookups require mb-user-agent to be configured."
        >⚠</span>
      </label>

      <!-- Auto sync (playlist only) -->
      <label v-if="isPlaylist" class="toggle-label">
        <span class="toggle-switch">
          <input v-model="autoSync" type="checkbox" :disabled="loading" />
          <span class="slider" />
        </span>
        <span>Auto sync</span>
      </label>

      <!-- Interval (playlist + autoSync only) -->
      <div v-if="isPlaylist && autoSync" class="interval-group">
        <input
          v-model.number="interval"
          class="interval-input"
          type="number"
          min="60"
          placeholder="86400"
          :disabled="loading"
        />
        <span class="interval-hint">seconds</span>
      </div>
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
  gap: 20px;
  flex-wrap: wrap;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
}

.toggle-switch {
  position: relative;
  width: 36px;
  height: 20px;
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
  border-radius: 20px;
  background: var(--border);
  transition: background 0.2s;
}

.slider::before {
  content: '';
  position: absolute;
  height: 14px;
  width: 14px;
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
  transform: translateX(16px);
  background: #fff;
}

.warn-icon {
  color: var(--warning);
  font-size: 13px;
  cursor: help;
}

.interval-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.interval-input {
  width: 90px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 7px 8px;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s;
}

.interval-input:focus {
  border-color: var(--accent);
}

.interval-hint {
  font-size: 12px;
  color: var(--text-muted);
}

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
</style>
