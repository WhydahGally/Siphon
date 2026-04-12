<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import QueueItem from './QueueItem.vue'

const emit = defineEmits(['has-jobs'])

// jobs: Array of job objects matching the GET /jobs response shape
const jobs = ref([])

// Map of job_id → EventSource for open SSE connections
const eventSources = {}

// True while cancel-all is in flight / draining
const cancelling = ref(false)

// --- Sort order (failed first, then active, then cancelled, then done) ---
const STATE_ORDER = { failed: 0, downloading: 1, pending: 2, cancelled: 3, done: 4 }

function sortedItems(items) {
  return [...items].sort((a, b) => (STATE_ORDER[a.state] ?? 9) - (STATE_ORDER[b.state] ?? 9))
}

const activeJob = computed(() => {
  return jobs.value.find(j => !isTerminal(j)) ?? jobs.value[0] ?? null
})

const singleJobs = computed(() => jobs.value.filter(j => j.playlist_id === null || j.playlist_id === undefined))
const playlistJobs = computed(() => jobs.value.filter(j => j.playlist_id !== null && j.playlist_id !== undefined))

function isTerminal(job) {
  return job.items.length > 0 && job.items.every(i => ['done', 'failed', 'cancelled'].includes(i.state))
}

// --- Button enabled states ---
const canCancel = computed(() =>
  !cancelling.value && playlistJobs.value.some(j => !isTerminal(j))
)
const canRetry = computed(() =>
  jobs.value.some(j => j.items.some(i => i.state === 'failed' || i.state === 'cancelled'))
)
const canClear = computed(() => {
  const allItems = jobs.value.flatMap(j => j.items)
  return allItems.some(i => ['done', 'failed', 'cancelled'].includes(i.state))
})

// True when the queue has no done items but still has failed/cancelled
const onlyFailedLeft = computed(() => {
  const allItems = jobs.value.flatMap(j => j.items)
  if (!allItems.length) return false
  const hasDone = allItems.some(i => i.state === 'done')
  const hasFailed = allItems.some(i => i.state === 'failed' || i.state === 'cancelled')
  return !hasDone && hasFailed
})

const clearTooltip = computed(() =>
  onlyFailedLeft.value ? 'Clear failed' : 'Clear finished'
)

// Reset cancelling state once all playlist jobs drain to terminal
watch(
  () => playlistJobs.value.every(j => j.items.length === 0 || isTerminal(j)),
  (allTerminal) => { if (allTerminal) cancelling.value = false }
)

// --- SSE ---
function connectSSE(jobId) {
  if (eventSources[jobId]) return
  const es = new EventSource(`/jobs/${jobId}/stream`)

  es.onmessage = (e) => {
    const event = JSON.parse(e.data)
    const job = jobs.value.find(j => j.job_id === event.job_id)
    if (!job) return
    const item = job.items.find(i => i.video_id === event.video_id)
    if (!item) return
    item.state = event.state
    item.renamed_to = event.renamed_to
    item.rename_tier = event.rename_tier
    item.error = event.error
  }

  es.addEventListener('done', () => {
    es.close()
    delete eventSources[jobId]
  })

  es.onerror = () => {
    es.close()
    delete eventSources[jobId]
  }

  eventSources[jobId] = es
}

// --- Init on mount ---
onMounted(async () => {
  try {
    const res = await fetch('/jobs')
    if (res.ok) {
      jobs.value = await res.json()
      if (jobs.value.length > 0) {
        emit('has-jobs')
      }
      for (const job of jobs.value) {
        if (!isTerminal(job)) {
          connectSSE(job.job_id)
        }
      }
    }
  } catch {
    // daemon not running yet — queue stays empty
  }
})

onUnmounted(() => {
  for (const es of Object.values(eventSources)) {
    es.close()
  }
})

// --- Called by Dashboard when a new job is created ---
async function addJob(jobId) {
  try {
    const res = await fetch('/jobs')
    if (res.ok) {
      jobs.value = await res.json()
    }
  } catch {}
  connectSSE(jobId)
}

// --- Cancel all active playlist jobs ---
async function cancelAll() {
  cancelling.value = true
  try {
    await fetch('/jobs/cancel-all', { method: 'POST' })
  } catch {
    cancelling.value = false
  }
}

// --- Retry failed and cancelled items ---
async function retryFailed() {
  const job = jobs.value.find(j => j.items.some(i => i.state === 'failed' || i.state === 'cancelled'))
  if (!job) return
  try {
    const res = await fetch(`/jobs/${job.job_id}/retry-failed`, { method: 'POST' })
    if (res.ok) {
      job.items
        .filter(i => i.state === 'failed' || i.state === 'cancelled')
        .forEach(i => { i.state = 'pending'; i.error = null })
      job.cancelled = false
      if (!eventSources[job.job_id]) connectSSE(job.job_id)
    }
  } catch {}
}

// --- Clear items (backend-backed so it survives page reload) ---
// When done items exist: only clear done (keep failed/cancelled for retry).
// When only failed/cancelled remain: clear everything.
async function clearDone() {
  const clearAll = onlyFailedLeft.value
  const jobsToClear = jobs.value.filter(j =>
    j.items.some(i => clearAll
      ? ['done', 'failed', 'cancelled'].includes(i.state)
      : i.state === 'done'
    )
  )
  for (const job of jobsToClear) {
    try {
      await fetch(`/jobs/${job.job_id}/clear-done${clearAll ? '?all=true' : ''}`, { method: 'POST' })
    } catch {}
  }
  // Re-fetch to get the authoritative state from the daemon
  try {
    const res = await fetch('/jobs')
    if (res.ok) jobs.value = await res.json()
  } catch {}
}

defineExpose({ addJob })
</script>

<template>
  <section v-if="jobs.length > 0" class="download-queue">
    <div class="queue-header">
      <div class="queue-title-row">
        <h2 class="section-title">Download queue</h2>
        <span v-if="activeJob" class="progress-summary">
          {{ activeJob.items.filter(i => i.state === 'done').length }} / {{ activeJob.original_total || activeJob.items.length }} downloaded
          <span v-if="activeJob.items.filter(i => i.state === 'failed').length > 0" class="failed-count">&nbsp;· {{ activeJob.items.filter(i => i.state === 'failed').length }} failed</span>
        </span>
      </div>
      <div class="queue-actions">
        <button
          class="btn-outline-error"
          :disabled="!canCancel"
          title="Abort pending downloads"
          @click="cancelAll"
        >
          <span v-if="cancelling" class="cancelling-text">Aborting…</span>
          <span v-else>Abort</span>
        </button>
        <button
          class="btn-outline"
          :disabled="!canRetry"
          title="Retry failed items"
          @click="retryFailed"
        >
          Retry
        </button>
        <button
          class="btn-outline"
          :disabled="!canClear"
          :title="clearTooltip"
          @click="clearDone"
        >
          Clear
        </button>
      </div>
    </div>

    <div class="queue-body">
      <div class="queue-inner">
        <div v-for="job in playlistJobs" :key="job.job_id" class="job-block">
          <div v-if="job.playlist_name" class="job-name">{{ job.playlist_name }}</div>
          <QueueItem
            v-for="item in sortedItems(job.items)"
            :key="item.video_id"
            :item="item"
            :job-id="job.job_id"
          />
        </div>

        <div v-if="singleJobs.length > 0" class="job-block">
          <div class="job-name">Default</div>
          <template v-for="job in singleJobs" :key="job.job_id">
            <QueueItem
              v-for="item in sortedItems(job.items)"
              :key="item.video_id"
              :item="item"
              :job-id="job.job_id"
            />
          </template>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.download-queue {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  gap: 12px;
  flex-wrap: wrap;
}

.queue-title-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
}

.progress-summary {
  font-size: 13px;
  color: var(--text-muted);
}

.failed-count {
  color: var(--error);
}

.queue-actions {
  display: flex;
  gap: 8px;
}

.btn-outline {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 500;
  transition: color 0.15s, border-color 0.15s;
  min-width: 60px;
}

.btn-outline:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--text-muted);
}

.btn-outline:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.btn-outline-error {
  background: none;
  border: 1px solid var(--error);
  color: var(--error);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 500;
  min-width: 60px;
  transition: background 0.15s;
}

.btn-outline-error:hover:not(:disabled) {
  background: var(--error-bg);
}

.btn-outline-error:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.cancelling-text {
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.queue-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: auto;
}

.queue-inner {
  width: max-content;
  min-width: 100%;
}

.job-block {
  padding: 6px 0;
}

.job-block + .job-block {
  border-top: 1px solid var(--border);
  margin-top: 2px;
  padding-top: 8px;
}

.job-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 4px 14px 6px;
}
</style>
