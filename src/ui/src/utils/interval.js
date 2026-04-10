/**
 * Convert a raw seconds value to a human-readable "every X<unit>" string.
 * @param {number|null} secs
 * @returns {string}
 */
export function secsToHuman(secs) {
  if (secs === null || secs === undefined) return '—'
  secs = Number(secs)
  if (secs < 60) {
    const n = secs
    return n === 1 ? 'Every second' : `Every ${n} seconds`
  }
  if (secs < 3600) {
    const n = Math.floor(secs / 60)
    return n === 1 ? 'Every minute' : `Every ${n} minutes`
  }
  if (secs < 86400) {
    const n = Math.floor(secs / 3600)
    return n === 1 ? 'Every hour' : `Every ${n} hours`
  }
  const n = Math.floor(secs / 86400)
  return n === 1 ? 'Every day' : `Every ${n} days`
}

/**
 * Convert a DD:HH:MM:SS string to total seconds.
 * Accepts 1–4 colon-separated parts:
 *   SS  →  s
 *   MM:SS  →  m*60 + s
 *   HH:MM:SS  →  h*3600 + m*60 + s
 *   DD:HH:MM:SS  →  d*86400 + h*3600 + m*60 + s
 * Returns null if the string is invalid or all zeros.
 * @param {string} str
 * @returns {number|null}
 */
export function ddhhmmssToSecs(str) {
  if (!str || typeof str !== 'string') return null
  const parts = str.trim().split(':').map(p => parseInt(p, 10))
  if (parts.length === 0 || parts.length > 4) return null
  if (parts.some(p => isNaN(p) || p < 0)) return null

  let total = 0
  const multipliers = [1, 60, 3600, 86400]
  for (let i = 0; i < parts.length; i++) {
    // parts are ordered most-significant last after reverse
    total += parts[parts.length - 1 - i] * multipliers[i]
  }
  return total > 0 ? total : null
}

/**
 * Convert a total seconds value to DD:HH:MM:SS string for use as an input default.
 * @param {number|null} secs
 * @returns {string}
 */
export function secsToDdhhmmss(secs) {
  if (!secs) return '00:00:00:00'
  secs = Number(secs)
  const d = Math.floor(secs / 86400)
  const h = Math.floor((secs % 86400) / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  return [d, h, m, s].map(v => String(v).padStart(2, '0')).join(':')
}
