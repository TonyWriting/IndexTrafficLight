const CACHE_EXPIRY_MS = 90 * 60 * 1000 // 90 minutes

interface CacheEntry<T> {
  data: T
  timestamp: number
}

export function removeCache(key: string): void {
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

/**
 * Get cached data if not expired.
 * Expired or malformed entries are deleted immediately.
 */
export function getCache<T>(key: string): T | null {
  try {
    const raw = uni.getStorageSync(key)
    if (!raw) return null
    const entry: CacheEntry<T> = JSON.parse(raw)
    if (Date.now() - entry.timestamp > CACHE_EXPIRY_MS) {
      removeCache(key)
      return null
    }
    return entry.data
  } catch {
    removeCache(key)
    return null
  }
}

/**
 * Set cache with current timestamp.
 */
export function setCache<T>(key: string, data: T): void {
  const entry: CacheEntry<T> = { data, timestamp: Date.now() }
  uni.setStorageSync(key, JSON.stringify(entry))
}
