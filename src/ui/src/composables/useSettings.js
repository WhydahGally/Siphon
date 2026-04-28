import { ref } from 'vue'

const autoRename = ref(true)
const browserLogs = ref(false)
const sponsorBlockEnabled = ref(true)
const cookiesEnabled = ref(false)
const cookieFileSet = ref(false)
const loaded = ref(false)

// Fetch immediately on module load — before any component renders.
Promise.all([
  fetch('/settings').then(r => r.ok ? r.json() : {}),
  fetch('/settings/cookie-file').then(r => r.ok ? r.json() : {}),
])
  .then(([s, c]) => {
    autoRename.value = s.auto_rename_default !== 'false'
    browserLogs.value = s.browser_logs === 'on'
    sponsorBlockEnabled.value = s.sponsorblock_enabled !== 'false'
    cookiesEnabled.value = s.cookies_enabled !== 'false'
    cookieFileSet.value = Boolean(c.set)
  })
  .catch(() => {})
  .finally(() => { loaded.value = true })

export function useSettings() {
  return { autoRename, browserLogs, sponsorBlockEnabled, cookiesEnabled, cookieFileSet, loaded }
}
