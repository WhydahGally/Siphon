<script setup>
import { ref } from 'vue'
import DownloadForm from './DownloadForm.vue'
import DownloadQueue from './DownloadQueue.vue'

const queueRef = ref(null)
const hasStarted = ref(false)

function onJobCreated(jobId) {
  hasStarted.value = true
  queueRef.value?.addJob(jobId)
}
</script>

<template>
  <div class="dashboard" :class="{ centered: !hasStarted }">
    <DownloadForm @job-created="onJobCreated" />
    <DownloadQueue ref="queueRef" @has-jobs="hasStarted = true" />
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 32px;
  transition: all 0.3s ease;
}

/* Before first job: vertically center the form in the remaining viewport */
.dashboard.centered {
  min-height: calc(100vh - 56px);
  justify-content: center;
}

/* Once started: normal top-padded layout */
.dashboard:not(.centered) {
  padding: 32px 0;
}
</style>
