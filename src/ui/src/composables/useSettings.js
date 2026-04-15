import { ref } from 'vue'

const autoRename = ref(true)
const browserLogs = ref(false)
const loaded = ref(false)

// Fetch immediately on module load — before any component renders.
fetch('/settings')
  .then(r => r.ok ? r.json() : {})
  .then(s => {
    autoRename.value = s.auto_rename_default !== 'false'
    browserLogs.value = s.browser_logs === 'on'
  })
  .catch(() => {})
  .finally(() => { loaded.value = true })

export function useSettings() {
  return { autoRename, browserLogs, loaded }
}
