// Backend dashboard snapshot refreshes at these Beijing-time minutes-of-day
// (cron trigger + buffer for the timer run and NAV fetch to finish).
const REFRESH_BUFFER_MIN = 15
const BACKEND_REFRESH_MINUTES_BJ = [8 * 60, 12 * 60, 21 * 60, 22 * 60 + 30]
  .map((m) => m + REFRESH_BUFFER_MIN) // 08:15 / 12:15 / 21:15 / 22:45
const BJ_OFFSET_MS = 8 * 60 * 60 * 1000
const DAY_MS = 86400000

interface CacheEntry<T> {
  data: T
  timestamp: number
}

function removeCache(key: string): void {
  try {
    uni.removeStorageSync(key)
  } catch {
    // Ignore storage cleanup errors.
  }
}

export function clearCacheKeys(shouldRemove: (key: string) => boolean): void {
  try {
    const { keys } = uni.getStorageInfoSync()
    keys.filter(shouldRemove).forEach(removeCache)
  } catch {
    // Ignore storage cleanup errors.
  }
}

// Timestamp (UTC ms) of the most recent backend refresh point at or before `nowMs`.
// Computed in Beijing time with plain arithmetic so it is independent of the
// device's local timezone.
function lastBackendRefresh(nowMs: number): number {
  const bj = nowMs + BJ_OFFSET_MS
  const dayStartBj = Math.floor(bj / DAY_MS) * DAY_MS
  const minutesIntoDay = (bj - dayStartBj) / 60000
  let lastMin = -Infinity
  for (const m of BACKEND_REFRESH_MINUTES_BJ) {
    if (m <= minutesIntoDay) lastMin = m
  }
  if (lastMin === -Infinity) {
    // Before today's first refresh point -> use yesterday's last one.
    const lastOfDay = BACKEND_REFRESH_MINUTES_BJ[BACKEND_REFRESH_MINUTES_BJ.length - 1]
    return dayStartBj - DAY_MS + lastOfDay * 60000 - BJ_OFFSET_MS
  }
  return dayStartBj + lastMin * 60000 - BJ_OFFSET_MS
}

/**
 * Get cached data while it is still aligned with the backend refresh schedule.
 * Stale (past a refresh point) or malformed entries are deleted immediately.
 */
export function getCache<T>(key: string): T | null {
  try {
    const raw = uni.getStorageSync(key)
    if (!raw) return null
    const entry = JSON.parse(raw) as Partial<CacheEntry<T>>
    if (
      !entry
      || typeof entry.timestamp !== 'number'
      || !Number.isFinite(entry.timestamp)
      || !('data' in entry)
    ) {
      removeCache(key)
      return null
    }
    // Invalidate once the cache predates the latest backend refresh point,
    // keeping cached data aligned with the backend's update schedule.
    if (entry.timestamp < lastBackendRefresh(Date.now())) {
      removeCache(key)
      return null
    }
    return entry.data as T
  } catch {
    removeCache(key)
    return null
  }
}

/**
 * Set cache with current timestamp.
 */
export function setCache<T>(key: string, data: T): void {
  try {
    const entry: CacheEntry<T> = { data, timestamp: Date.now() }
    uni.setStorageSync(key, JSON.stringify(entry))
  } catch {
    // Ignore storage quota or platform storage errors.
  }
}
