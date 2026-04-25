<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import NavBar from './components/NavBar.vue'
import Dashboard from './components/Dashboard.vue'
import Library from './components/Library.vue'
import Settings from './components/Settings.vue'
import ToastContainer from './components/ToastContainer.vue'
import { useSettings } from './composables/useSettings.js'

const currentPage = ref('dashboard')
const { browserLogs } = useSettings()

let logSource = null

function connectLogStream() {
  if (logSource) { logSource.close(); logSource = null }
  logSource = new EventSource('/logs/stream')
  logSource.onmessage = (e) => {
    try {
      const { level, name, msg } = JSON.parse(e.data)
      const tag = `[${name}] ${msg}`
      if (level === 'DEBUG') console.debug(tag)
      else if (level === 'INFO') console.info(tag)
      else if (level === 'WARNING') console.warn(tag)
      else console.error(tag)
    } catch { /* malformed event */ }
  }
  logSource.onerror = () => { logSource.close(); logSource = null }
}

function disconnectLogStream() {
  if (logSource) { logSource.close(); logSource = null }
}

watch(browserLogs, (val) => {
  if (val) connectLogStream()
  else disconnectLogStream()
})

onMounted(async () => {
  try {
    const res = await fetch('/info')
    if (res.ok) {
      const { download_dir, db_dir } = await res.json()
      console.info('[siphon] Download directory:', download_dir)
      console.info('[siphon] DB & logs directory:', db_dir)
    }
  } catch {
    // daemon not reachable yet
  }
  if (browserLogs.value) connectLogStream()
})

onUnmounted(() => {
  disconnectLogStream()
})
</script>

<template>
  <div class="app">
    <NavBar :current-page="currentPage" @navigate="currentPage = $event" />
    <main class="main-content">
      <Dashboard v-if="currentPage === 'dashboard'" />
      <Library v-else-if="currentPage === 'library'" />
      <Settings v-else-if="currentPage === 'settings'" />
    </main>
    <ToastContainer />
  </div>
</template>

<style>
.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.main-content {
  flex: 1;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
  padding: 0 24px;
}

@media (max-width: 640px) {
  .main-content {
    padding: 0 16px;
  }
}
</style>
