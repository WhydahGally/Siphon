import { ref } from 'vue'

const autoRename = ref(true)
const browserLogs = ref(false)
const sponsorBlockEnabled = ref(true)
const sbCategoriesEmpty = ref(false)
const cookiesEnabled = ref(false)
const cookieFileSet = ref(false)
const mbUserAgentMissing = ref(false)
const sbRequireForSync = ref(false)
const loaded = ref(false)

// Fetch immediately on module load — before any component renders.
Promise.all([
  fetch('/settings').then(r => r.ok ? r.json() : {}),
  fetch('/settings/cookie-file').then(r => r.ok ? r.json() : {}),
  fetch('/settings/mb-user-agent').then(r => r.ok ? r.json() : {}),
])
  .then(([s, c, mb]) => {
    autoRename.value = s.auto_rename_default !== 'false'
    browserLogs.value = s.browser_logs === 'on'
    sponsorBlockEnabled.value = s.sponsorblock_enabled !== 'false'
    cookiesEnabled.value = s.cookies_enabled !== 'false'
    cookieFileSet.value = Boolean(c.set)
    mbUserAgentMissing.value = !mb.value
    try {
      const cats = s.sponsorblock_categories ? JSON.parse(s.sponsorblock_categories) : null
      sbCategoriesEmpty.value = Array.isArray(cats) && cats.length === 0
    } catch { sbCategoriesEmpty.value = false }
    sbRequireForSync.value = s.sb_require_for_sync === 'true'
  })
  .catch(() => {})
  .finally(() => { loaded.value = true })

export function useSettings() {
  return { autoRename, browserLogs, sponsorBlockEnabled, sbCategoriesEmpty, cookiesEnabled, cookieFileSet, mbUserAgentMissing, sbRequireForSync, loaded }
}
