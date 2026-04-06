<script setup>
import { ref } from 'vue'
import DownloadForm from './DownloadForm.vue'
import DownloadQueue from './DownloadQueue.vue'

const queueRef = ref(null)

function onJobCreated(jobId) {
  queueRef.value?.addJob(jobId)
}
</script>

<template>
  <div class="dashboard">
    <DownloadForm @job-created="onJobCreated" />
    <DownloadQueue ref="queueRef" />
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 32px;
}
</style>
