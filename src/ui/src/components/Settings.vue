<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import ConfirmButton from './ConfirmButton.vue'
import { useToast } from '../composables/useToast.js'
import { ddhhmmssToSecs, secsToDdhhmmss, secsToHuman } from '../utils/interval.js'
import { useSettings } from '../composables/useSettings.js'

const { showToast } = useToast()

// ── State ──────────────────────────────────────────────────────────────────────
const maxConcurrent = ref(5)
const intervalSecs = ref(86400)
const editingInterval = ref(false)
const intervalInput = ref('')
const { autoRename: autoRenameGlobal, browserLogs, loaded: settingsLoaded } = useSettings()
const mbUserAgent = ref('')
const isDark = ref(true)
const logLevel = ref('INFO')
const version = ref({ siphon: '—', yt_dlp: '—' })
const logsDir = ref('')

const intervalDisplay = computed(() => secsToHuman(intervalSecs.value))

// ── Load on mount ───────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const res = await fetch('/settings')
    if (res.ok) {
      const s = await res.json()
      if (s.max_concurrent_downloads) maxConcurrent.value = parseInt(s.max_concurrent_downloads, 10) || 5
      if (s.check_interval)           intervalSecs.value = parseInt(s.check_interval, 10) || 86400
      if (s.auto_rename_default === 'false') autoRenameGlobal.value = false
      if (s.mb_user_agent)            mbUserAgent.value = s.mb_user_agent
      if (s.theme)                    isDark.value = s.theme !== 'light'
      if (s.log_level)                logLevel.value = s.log_level
    }
  } catch { /* daemon not reachable */ }

  try {
    const res = await fetch('/version')
    if (res.ok) version.value = await res.json()
  } catch {}

  try {
    const res = await fetch('/info')
    if (res.ok) {
      const data = await res.json()
      logsDir.value = data.logs_dir || data.db_dir || ''
    }
  } catch {}
})

// ── Helpers ─────────────────────────────────────────────────────────────────────
async function saveSetting(key, value, silent = false) {
  try {
    const res = await fetch(`/settings/${key}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: String(value) }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      showToast(data.detail || 'Failed to save.', 'error')
    } else if (!silent) {
      showToast('Saved.', 'success')
    }
  } catch {
    showToast('Could not reach the daemon.', 'error')
  }
}

// ── Downloads ───────────────────────────────────────────────────────────────────
function onMaxConcurrentChange() { saveSetting('max-concurrent-downloads', maxConcurrent.value, true) }

const intervalEditRef = ref(null)
let _intervalClickOutside = null

function openIntervalEdit() {
  intervalInput.value = secsToDdhhmmss(intervalSecs.value)
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
  if (secs === null) return
  intervalSecs.value = secs
  saveSetting('interval', secs)
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

function onAutoRenameToggle() {
  autoRenameGlobal.value = !autoRenameGlobal.value
  saveSetting('auto-rename', autoRenameGlobal.value ? 'true' : 'false', true)
}

// ── MusicBrainz ──────────────────────────────────────────────────────────────────
function saveMbUserAgent() { saveSetting('mb-user-agent', mbUserAgent.value) }

// ── Noise patterns ───────────────────────────────────────────────────────────────
const noisePatternsOpen = ref(false)
const noisePatternsText = ref('')
const noisePatternsStored = ref('')

async function openNoisePatterns() {
  noisePatternsOpen.value = true
  try {
    const res = await fetch('/settings/title-noise-patterns')
    if (res.ok) {
      const data = await res.json()
      if (data.value) {
        const arr = JSON.parse(data.value)
        noisePatternsText.value = arr.join('\n')
        noisePatternsStored.value = noisePatternsText.value
      } else {
        noisePatternsText.value = ''
        noisePatternsStored.value = ''
      }
    }
  } catch { /* daemon not reachable */ }
}

function cancelNoisePatterns() {
  noisePatternsText.value = noisePatternsStored.value
  noisePatternsOpen.value = false
}

async function saveNoisePatterns() {
  const patterns = noisePatternsText.value
    .split('\n')
    .map(l => l.trim())
    .filter(l => l.length > 0)
  try {
    const res = await fetch('/settings/title-noise-patterns', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: JSON.stringify(patterns) }),
    })
    if (res.ok) {
      noisePatternsStored.value = noisePatternsText.value
      showToast('Saved.', 'success')
      noisePatternsOpen.value = false
    } else {
      const data = await res.json().catch(() => ({}))
      showToast(data.detail || 'Failed to save.', 'error')
    }
  } catch {
    showToast('Could not reach the daemon.', 'error')
  }
}

// ── Appearance ───────────────────────────────────────────────────────────────────
function onThemeToggle() {
  isDark.value = !isDark.value
  if (!isDark.value) {
    document.documentElement.dataset.theme = 'light'
  } else {
    delete document.documentElement.dataset.theme
  }
  saveSetting('theme', isDark.value ? 'dark' : 'light', true)
}

// ── About ─────────────────────────────────────────────────────────────────────────
function onLogLevelChange() { saveSetting('log-level', logLevel.value, true) }

// ── Debugging ─────────────────────────────────────────────────────────────────────
function onBrowserLogsToggle() {
  browserLogs.value = !browserLogs.value
  saveSetting('browser-logs', browserLogs.value ? 'on' : 'off', true)
}

// ── Danger zone ───────────────────────────────────────────────────────────────────
async function handleDeleteAllPlaylists() {
  try {
    const res = await fetch('/playlists', { method: 'DELETE' })
    if (res.status === 204 || res.ok) {
      showToast('All playlists deleted.', 'success')
    } else {
      showToast('Failed to delete playlists.', 'error')
    }
  } catch { showToast('Could not reach the daemon.', 'error') }
}

async function handleFactoryReset() {
  try {
    const res = await fetch('/factory-reset', { method: 'POST' })
    if (res.status === 204 || res.ok) {
      showToast('Factory reset complete. Reloading…', 'success')
      setTimeout(() => window.location.reload(), 1500)
    } else {
      showToast('Factory reset failed.', 'error')
    }
  } catch { showToast('Could not reach the daemon.', 'error') }
}
</script>

<template>
  <div class="settings-page">
    <h2 class="page-title">Settings</h2>

    <!-- ── Downloads ──────────────────────────────────────────────────────── -->
    <section class="settings-section">
      <h3 class="section-heading">Downloads</h3>

      <div class="setting-row">
        <div class="setting-label-col">
          <span class="setting-label">Max concurrent downloads</span>
          <span class="setting-desc">
            How many simultaneous downloads. 
            Higher numbers may get blocked.
          </span>
        </div>
        <div class="setting-control-col">
          <select v-model="maxConcurrent" class="select" @change="onMaxConcurrentChange">
            <option v-for="n in 10" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-label-col">
          <span class="setting-label">Default sync interval</span>
          <span class="setting-desc">
            How often to check all watched playlists for new videos.
            Per-playlist intervals takes precedence.
          </span>
        </div>
        <div ref="intervalEditRef" class="setting-control-col interval-control">
          <template v-if="!editingInterval">
            <span class="interval-display" @click="openIntervalEdit">
              {{ intervalDisplay }}
              <svg class="pencil-icon" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </span>
          </template>
          <template v-else>
            <input
              v-model="intervalInput"
              class="interval-input"
              placeholder="DD:HH:MM:SS"
              title="Format - DD:HH:MM:SS"
              @keydown.enter.prevent="saveInterval"
              @keydown.escape="cancelIntervalEdit"
            />
            <button class="btn-save" @mousedown.stop @click="saveInterval">Save</button>
          </template>
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-label-col">
          <span class="setting-label">Auto rename</span>
          <span class="setting-desc">Default state of the <code>Auto rename</code> checkbox when adding a new download.</span>
        </div>
        <div class="setting-control-col">
          <label v-if="settingsLoaded" class="toggle-switch">
            <input type="checkbox" :checked="autoRenameGlobal" @change="onAutoRenameToggle" />
            <span class="slider" />
          </label>
        </div>
      </div>
    </section>

    <!-- ── Auto Renamer ───────────────────────────────────────────────────── -->
    <section class="settings-section">
      <h3 class="section-heading">Auto Renamer</h3>

      <div class="setting-row setting-row--block">
        <div class="setting-label-col">
          <span class="setting-label">MusicBrainz user-agent</span>
          <span class="setting-desc">
            Required for metadata lookups during auto rename.
            Format: <code>AppName/1.0 (you@example.com)</code><br />
            <span class="setting-hint">Setting this will dismiss the ⚠ warning on Dashboard.</span>
          </span>
        </div>
        <div class="setting-control-col mb-input-row">
          <input
            v-model="mbUserAgent"
            class="text-input"
            placeholder="Siphon/1.0 (you@example.com)"
            @keydown.enter="saveMbUserAgent"
          />
          <button class="btn-primary-sm" @click="saveMbUserAgent">Save</button>
        </div>
      </div>

      <div class="noise-disclosure" :class="{ 'noise-disclosure--open': noisePatternsOpen }">
        <div class="noise-disclosure-header" @click="noisePatternsOpen ? cancelNoisePatterns() : openNoisePatterns()">
          <div class="setting-label-col">
            <span class="setting-label">Title noise patterns</span>
            <span class="setting-desc">
              Regex patterns that strip YouTube noise suffixes (e.g. <code>(Official Video)</code>, <code>[Lyric Video]</code>)
              from filenames.
            </span>
          </div>
          <button class="noise-expand-strip" :class="{ 'is-expanded': noisePatternsOpen }">
            <span class="chevron">›</span>
          </button>
        </div>
        <div v-if="noisePatternsOpen" class="noise-disclosure-body">
          <span class="setting-desc" style="margin-bottom: 6px; display: block;">
            Each pattern matches content inside <code>( )</code> or <code>[ ]</code> at the end of a title.
            When unset, built-in defaults are used.
          </span>
          <textarea
            v-model="noisePatternsText"
            class="noise-textarea"
            placeholder="One pattern per line, e.g.&#10;official video&#10;lyric video"
            rows="6"
          />
          <span v-if="!noisePatternsStored" class="setting-desc noise-default-note">
            No patterns saved — built-in defaults are currently active.
          </span>
          <div class="noise-actions">
            <button class="btn-primary-sm" @click="saveNoisePatterns">Save</button>
            <button class="btn-cancel-sm" @click="cancelNoisePatterns">Cancel</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ── Appearance ─────────────────────────────────────────────────────── -->
    <section class="settings-section">
      <h3 class="section-heading">Appearance</h3>

      <div class="setting-row">
        <div class="setting-label-col">
          <span class="setting-label">Theme</span>
          <span class="setting-desc">Switch between dark and light colour scheme.</span>
        </div>
        <div class="setting-control-col theme-toggle-row">
          <span class="theme-label" :class="{ active: isDark }">Dark</span>
          <label class="toggle-switch">
            <input type="checkbox" :checked="!isDark" @change="onThemeToggle" />
            <span class="slider" />
          </label>
          <span class="theme-label" :class="{ active: !isDark }">Light</span>
        </div>
      </div>
    </section>

    <!-- ── About ───────────────────────────────────────────────────────────── -->
    <section class="settings-section">
      <h3 class="section-heading">About</h3>

      <div class="about-grid">
        <span class="about-key">Siphon</span>
        <span class="about-val">{{ version.siphon }}</span>

        <span class="about-key">YT-DLP</span>
        <span class="about-val">{{ version.yt_dlp }}</span>

        <span class="about-key">Source</span>
        <a
          class="about-link"
          href="https://github.com/WhydahGally/Siphon"
          target="_blank"
          rel="noopener noreferrer"
        >github.com/WhydahGally/Siphon ↗</a>
      </div>

      <div class="about-grid" style="border-top: 1px solid var(--border); padding-top: 12px;">
        <span class="about-key" :title="logsDir + '/siphon.log'">Log level</span>
        <select v-model="logLevel" class="select select--sm" :title="logsDir + '/siphon.log'" @change="onLogLevelChange">
          <option v-for="lvl in ['DEBUG', 'INFO', 'WARNING', 'ERROR']" :key="lvl" :value="lvl">{{ lvl }}</option>
        </select>

        <span class="about-key" title="Stream daemon logs to the browser's developer console.">Browser logs</span>
        <label class="toggle-switch" title="Stream daemon logs to the browser's developer console.">
          <input type="checkbox" :checked="browserLogs" @change="onBrowserLogsToggle" />
          <span class="slider" />
        </label>
      </div>
    </section>

    <!-- ── Danger Zone ─────────────────────────────────────────────────────── -->
    <section class="settings-section settings-section--danger">
      <h3 class="section-heading section-heading--danger">⚠ Danger Zone</h3>

      <div class="danger-row">
        <div class="danger-label-col">
          <span class="setting-label">Delete Playlists</span>
          <span class="setting-desc">
            Removes all playlists and their sync history.
            Settings are kept. Your downloaded files are not affected.
          </span>
        </div>
        <div class="danger-control-col">
          <ConfirmButton
            label="Delete Playlists"
            danger-label="Yes, delete all"
            @confirm="handleDeleteAllPlaylists"
          />
        </div>
      </div>

      <div class="danger-row">
        <div class="danger-label-col">
          <span class="setting-label">Factory Reset</span>
          <span class="setting-desc">
            Wipes everything — playlists, history, and all settings.
            Like a fresh install. Your downloaded files are not affected.
          </span>
        </div>
        <div class="danger-control-col">
          <ConfirmButton
            label="Factory Reset"
            danger-label="Yes, reset everything"
            @confirm="handleFactoryReset"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 32px 0 64px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
}

/* ── Sections ───────────────────────────────────────────────────────────── */
.settings-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.settings-section--danger {
  border-color: rgba(224, 85, 85, 0.3);
}

.section-heading {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 14px 20px 10px;
  border-bottom: 1px solid var(--border);
}

.section-heading--danger {
  color: var(--error);
}

.subsection-heading {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 14px 20px 6px;
  margin: 0;
  border-top: 1px solid var(--border);
}

.info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  height: 12px;
  margin-left: 4px;
  border-radius: 50%;
  border: 1px solid var(--text-muted);
  color: var(--text-muted);
  font-size: 8px;
  font-weight: 700;
  cursor: help;
  flex-shrink: 0;
  vertical-align: middle;
}

/* ── Setting rows ──────────────────────────────────────────────────────── */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.setting-row:last-child { border-bottom: none; }

.setting-row--block {
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}

.setting-label-col {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
  min-width: 0;
}

.setting-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
}

.setting-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.setting-hint {
  color: var(--warning);
}

code {
  background: var(--surface-2);
  border-radius: 3px;
  padding: 1px 5px;
  font-size: 11px;
  color: var(--text);
  font-family: ui-monospace, 'Cascadia Code', monospace;
}

.setting-control-col {
  flex-shrink: 0;
}

/* ── Select ────────────────────────────────────────────────────────────── */
.select {
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 13px;
  min-width: 80px;
}

.select--sm {
  padding: 4px 8px;
  font-size: 12px;
  min-width: 0;
  width: fit-content;
}

/* ── Toggle switch ─────────────────────────────────────────────────────── */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  flex-shrink: 0;
}

.toggle-switch input { opacity: 0; width: 0; height: 0; }

.slider {
  position: absolute;
  inset: 0;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 20px;
  transition: background 0.2s, border-color 0.2s;
  cursor: pointer;
}
.slider::before {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  left: 2px;
  top: 2px;
  background: var(--text-muted);
  border-radius: 50%;
  transition: transform 0.2s, background 0.2s;
}
.toggle-switch input:checked + .slider { background: var(--accent); border-color: var(--accent); }
.toggle-switch input:checked + .slider::before { background: #fff; transform: translateX(16px); }

/* ── Interval ──────────────────────────────────────────────────────────── */
.interval-control {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.interval-display {
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
}
.interval-display:hover { color: var(--text); }

.pencil-icon { opacity: 0.5; flex-shrink: 0; }

.interval-input {
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 5px 10px;
  font-size: 13px;
  width: 130px;
}
.interval-input:focus { outline: none; border-color: var(--accent); }

/* ── Buttons ────────────────────────────────────────────────────────────── */
.btn-save, .btn-cancel-sm, .btn-primary-sm {
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--border);
  white-space: nowrap;
}
.btn-save, .btn-primary-sm {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.btn-save:hover, .btn-primary-sm:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
.btn-cancel-sm { background: none; color: var(--text-muted); }
.btn-cancel-sm:hover { color: var(--text); border-color: var(--text-muted); }

/* ── MusicBrainz input ──────────────────────────────────────────────────── */
.mb-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.text-input {
  flex: 1;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 13px;
}
.text-input:focus { outline: none; border-color: var(--accent); }
.text-input::placeholder { color: var(--text-muted); }

/* ── Noise patterns editor ───────────────────────────────────────────────── */
.noise-disclosure {
  border-bottom: 1px solid var(--border);
}
.noise-disclosure:last-child { border-bottom: none; }

.noise-disclosure-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
}
.noise-disclosure-header:hover { background: var(--surface-2); }

.noise-expand-strip {
  flex-shrink: 0;
  width: 44px;
  align-self: stretch;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-left: 1px solid var(--border);
  cursor: pointer;
  padding: 0;
  margin: -16px -20px -16px 0;
}
.noise-expand-strip .chevron {
  font-size: 22px;
  color: var(--text-muted);
  transition: transform 0.2s ease, color 0.2s ease, text-shadow 0.2s ease;
  display: inline-block;
}
.noise-expand-strip.is-expanded .chevron {
  transform: rotate(90deg);
}
.noise-expand-strip:hover .chevron {
  color: var(--accent);
  text-shadow: 0 0 10px var(--accent), 0 0 20px rgba(124, 106, 247, 0.4);
}

.noise-disclosure-body {
  padding: 0 20px 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.noise-textarea {
  width: 100%;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-size: 12px;
  font-family: ui-monospace, 'Cascadia Code', monospace;
  resize: vertical;
  min-height: 100px;
  box-sizing: border-box;
}
.noise-textarea:focus { outline: none; border-color: var(--accent); }

.noise-default-note {
  font-style: italic;
}

.noise-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* ── Theme toggle ────────────────────────────────────────────────────────── */
.theme-toggle-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.theme-label {
  font-size: 13px;
  color: var(--text-muted);
  transition: color 0.15s;
}
.theme-label.active { color: var(--text); font-weight: 500; }

/* ── About grid ──────────────────────────────────────────────────────────── */
.about-grid {
  display: grid;
  grid-template-columns: 110px 1fr;
  row-gap: 14px;
  column-gap: 16px;
  padding: 16px 20px;
  align-items: center;
  justify-items: end;
}

.about-key {
  font-size: 13px;
  color: var(--text-muted);
  justify-self: start;
}

.about-val {
  font-size: 13px;
  color: var(--text);
}

.about-link {
  font-size: 13px;
  color: var(--accent);
  text-decoration: none;
}
.about-link:hover { text-decoration: underline; }

/* ── Danger zone rows ────────────────────────────────────────────────────── */
.danger-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.danger-row:last-child { border-bottom: none; }

.danger-label-col {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
  min-width: 0;
}

.danger-control-col { flex-shrink: 0; }
</style>

