import type { EtfInfo, EtfPremiumHistory } from '../types'
import { clearCacheKeys, getCache, setCache } from './cache'
import mockEtfs from '../mock/etfs.json'
import mockPremiumHistory from '../mock/premium-history.json'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const MOCK_MODE = import.meta.env.VITE_USE_MOCK
const USE_MOCK = MOCK_MODE === 'true' || (MOCK_MODE !== 'false' && !BASE_URL)
const DISABLE_CACHE = import.meta.env.VITE_DISABLE_CACHE === 'true'

const CACHE_VERSION = 'v5'
const CACHE_KEY_ETFS = `cache_etfs_${CACHE_VERSION}`
const CACHE_KEY_HISTORY = `cache_etf_premium_history_${CACHE_VERSION}_`
const CACHE_KEY_ETFS_PREFIX = 'cache_etfs'
const LEGACY_CACHE_KEY_HISTORY_PREFIX = 'cache_etf_premium_history_'
const LEGACY_INDEX_CACHE_KEY = 'cache_indices'
const LEGACY_INDEX_HISTORY_PREFIX = 'cache_history_'
const AUTO_REFRESH_INTERVAL_MS = 60 * 60 * 1000
const HISTORY_REFRESH_CONCURRENCY = 3

export const PREMIUM_CACHE_UPDATED_EVENT = 'premium-cache-updated'

let legacyCacheCleared = false
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
let warmupPromise: Promise<void> | null = null
let refreshAllPromise: Promise<void> | null = null
const inFlight = new Map<string, Promise<unknown>>()

function request<T>(url: string): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}${url}`,
      method: 'GET',
      success: (res: any) => {
        if (res.statusCode === 200) {
          resolve(res.data as T)
        } else {
          reject(new Error(`HTTP ${res.statusCode}`))
        }
      },
      fail: (err: any) => reject(err),
    })
  })
}

function mockHistoryFor(code: string): EtfPremiumHistory {
  const all = mockPremiumHistory as Record<string, EtfPremiumHistory>
  return all[code] || {
    code,
    name: code,
    short_name: code,
    count: 0,
    data: [],
  }
}

function singleFlight<T>(key: string, task: () => Promise<T>): Promise<T> {
  const running = inFlight.get(key) as Promise<T> | undefined
  if (running) return running

  const promise = task().finally(() => {
    inFlight.delete(key)
  })

  inFlight.set(key, promise)
  return promise
}

async function runWithConcurrency<T>(
  items: T[],
  limit: number,
  worker: (item: T) => Promise<void>,
): Promise<void> {
  let cursor = 0

  async function runNext(): Promise<void> {
    const current = cursor
    cursor += 1
    if (current >= items.length) return
    await worker(items[current])
    await runNext()
  }

  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, runNext),
  )
}

function emitCacheUpdated(): void {
  try {
    uni.$emit(PREMIUM_CACHE_UPDATED_EVENT)
  } catch {
    // Ignore event errors in non-UI contexts.
  }
}

function logBackgroundError(message: string, err: unknown): void {
  console.warn(message, err)
}

function clearLegacyCacheOnce(): void {
  if (legacyCacheCleared) return
  legacyCacheCleared = true

  clearCacheKeys((key) => (
    (
      key.startsWith(CACHE_KEY_ETFS_PREFIX)
      && key !== CACHE_KEY_ETFS
    )
    || (
      key.startsWith(LEGACY_CACHE_KEY_HISTORY_PREFIX)
      && !key.startsWith(CACHE_KEY_HISTORY)
    )
    || key === LEGACY_INDEX_CACHE_KEY
    || key.startsWith(LEGACY_INDEX_HISTORY_PREFIX)
  ))
}

export async function fetchEtfs(forceRefresh = false): Promise<EtfInfo[]> {
  if (USE_MOCK) return mockEtfs as EtfInfo[]
  clearLegacyCacheOnce()

  if (!forceRefresh && !DISABLE_CACHE) {
    const cached = getCache<EtfInfo[]>(CACHE_KEY_ETFS)
    if (cached) return cached
  }

  return singleFlight('etfs', async () => {
    const data = await request<EtfInfo[]>('/api/etfs')
    if (!DISABLE_CACHE) setCache(CACHE_KEY_ETFS, data)
    return data
  }).catch(() => {
    throw new Error('ETF 列表加载失败')
  })
}

export async function fetchPremiumHistory(
  code: string,
  forceRefresh = false,
): Promise<EtfPremiumHistory> {
  if (USE_MOCK) return mockHistoryFor(code)
  clearLegacyCacheOnce()

  const cacheKey = CACHE_KEY_HISTORY + code

  if (!forceRefresh && !DISABLE_CACHE) {
    const cached = getCache<EtfPremiumHistory>(cacheKey)
    if (cached) return cached
  }

  return singleFlight(`history:${code}`, async () => {
    const data = await request<EtfPremiumHistory>(`/api/etfs/history?code=${encodeURIComponent(code)}`)
    if (!DISABLE_CACHE) setCache(cacheKey, data)
    return data
  }).catch(() => {
    throw new Error(`${code} 溢价历史加载失败`)
  })
}

export function warmPremiumCache(): void {
  if (USE_MOCK || warmupPromise) return

  warmupPromise = (async () => {
    const list = await fetchEtfs(false)
    await runWithConcurrency(list, HISTORY_REFRESH_CONCURRENCY, async (info) => {
      try {
        await fetchPremiumHistory(info.code, false)
      } catch (err) {
        logBackgroundError(`Failed to warm ETF history cache for ${info.code}`, err)
      }
    })
    emitCacheUpdated()
  })()
    .catch((err) => {
      logBackgroundError('Failed to warm ETF premium cache', err)
    })
    .finally(() => {
      warmupPromise = null
    })
}

export async function refreshAllPremiumData(): Promise<void> {
  if (USE_MOCK) return
  if (refreshAllPromise) return refreshAllPromise

  refreshAllPromise = (async () => {
    const list = await fetchEtfs(true)
    await runWithConcurrency(list, HISTORY_REFRESH_CONCURRENCY, async (info) => {
      try {
        await fetchPremiumHistory(info.code, true)
      } catch (err) {
        logBackgroundError(`Failed to refresh ETF history cache for ${info.code}`, err)
      }
    })
    emitCacheUpdated()
  })()
    .catch((err) => {
      logBackgroundError('Failed to refresh ETF premium cache', err)
    })
    .finally(() => {
      refreshAllPromise = null
    })

  return refreshAllPromise
}

export function startPremiumAutoRefresh(): void {
  if (USE_MOCK) return
  warmPremiumCache()

  if (autoRefreshTimer) return
  autoRefreshTimer = setInterval(() => {
    void refreshAllPremiumData()
  }, AUTO_REFRESH_INTERVAL_MS)
}

export function stopPremiumAutoRefresh(): void {
  if (!autoRefreshTimer) return
  clearInterval(autoRefreshTimer)
  autoRefreshTimer = null
}
