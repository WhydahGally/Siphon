<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import QueueItem from './QueueItem.vue'

const emit = defineEmits(['has-jobs'])

// jobs: Array of job objects matching the GET /jobs response shape
const jobs = ref([])

// Map of job_id → EventSource for open SSE connections
const eventSources = {}

// --- Sort order helper ---
const STATE_ORDER = { downloading: 0, pending: 1, done: 2, failed: 3 }

function sortedItems(items) {
  return [...items].sort((a, b) => (STATE_ORDER[a.state] ?? 9) - (STATE_ORDER[b.state] ?? 9))
}

// Active job for progress summary: most recent non-terminal job, or the last job
const activeJob = computed(() => {
  return jobs.value.find(j => !isTerminal(j)) ?? jobs.value[0] ?? null
})

function isTerminal(job) {
  return job.items.length > 0 && job.items.every(i => i.state === 'done' || i.state === 'failed')
}

// --- SSE ---
function connectSSE(jobId) {
  if (eventSources[jobId]) return // already connected
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
      // Reconnect SSE for any in-progress jobs
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

// --- Retry failed ---
async function retryFailed(jobId) {
  try {
    const res = await fetch(`/jobs/${jobId}/retry-failed`, { method: 'POST' })
    if (res.ok) {
      const job = jobs.value.find(j => j.job_id === jobId)
      if (job) {
        job.items.filter(i => i.state === 'failed').forEach(i => {
          i.state = 'pending'
          i.error = null
        })
      }
      if (!eventSources[jobId]) connectSSE(jobId)
    }
  } catch {}
}

// --- Clear terminal jobs ---
async function clearList() {
  const terminal = jobs.value.filter(j => isTerminal(j))
  for (const job of terminal) {
    try {
      await fetch(`/jobs/${job.job_id}`, { method: 'DELETE' })
    } catch {}
  }
  jobs.value = jobs.value.filter(j => !isTerminal(j))
}

defineExpose({ addJob })
</script>

<template>
  <section v-if="jobs.length > 0" class="download-queue">
    <div class="queue-header">
      <div class="queue-title-row">
        <h2 class="section-title">Downloads</h2>
        <span v-if="activeJob" class="progress-summary">
          {{ activeJob.done }} / {{ activeJob.total }} downloaded
          <span v-if="activeJob.failed > 0" class="failed-count">&nbsp;· {{ activeJob.failed }} failed</span>
        </span>
      </div>
      <div class="queue-actions">
        <button
          v-if="jobs.some(j => j.items.some(i => i.state === 'failed'))"
          class="btn-outline-error"
          @click="retryFailed(jobs.find(j => j.items.some(i => i.state === 'failed')).job_id)"
        >
          Retry failed
        </button>
        <button
          v-if="jobs.some(j => isTerminal(j))"
          class="btn-outline"
          @click="clearList"
        >
          Clear list
        </button>
      </div>
    </div>

    <div v-for="job in jobs" :key="job.job_id" class="job-block">
      <div v-if="job.playlist_name" class="job-name">{{ job.playlist_name }}</div>
      <QueueItem
        v-for="item in sortedItems(job.items)"
        :key="item.video_id"
        :item="item"
        :job-id="job.job_id"
        @retry="retryFailed"
      />
    </div>
  </section>
</template>

<style scoped>
.download-queue {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
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
}

.btn-outline:hover {
  color: var(--text);
  border-color: var(--text-muted);
}

.btn-outline-error {
  background: none;
  border: 1px solid var(--error);
  color: var(--error);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.15s;
}

.btn-outline-error:hover {
  background: var(--error-bg);
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
