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
    <DownloadQueue ref="queueRef" @has-jobs="hasStarted = true" />
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding: 32px 0;
  max-height: calc(100vh - 56px);
  box-sizing: border-box;
}
</style>
