import type {
  DashboardGroup,
  DashboardItem,
  DashboardSnapshot,
  DashboardStats,
  EtfInfo,
  EtfPremiumHistory,
  PremiumRange,
} from '../types'
import { RANGE_OPTIONS } from '../types'
import { clearCacheKeys, getCache, setCache } from './cache'
import mockEtfs from '../mock/etfs.json'
import mockPremiumHistory from '../mock/premium-history.json'
import { summarizePremium } from '../utils/premium'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const MOCK_MODE = import.meta.env.VITE_USE_MOCK
const USE_MOCK = MOCK_MODE === 'true' || (MOCK_MODE !== 'false' && !BASE_URL)
const DISABLE_CACHE = import.meta.env.VITE_DISABLE_CACHE === 'true'

const CACHE_VERSION = 'v11'
const CACHE_KEYS = {
  dashboard: `cache_dashboard_${CACHE_VERSION}`,
  historyPrefix: `cache_etf_premium_history_${CACHE_VERSION}_`,
} as const
const PREMIUM_CACHE_MATCHERS = [
  (key: string) => key.startsWith('cache_dashboard_'),
  (key: string) => key.startsWith('cache_etf_premium_history_'),
]
const STALE_CACHE_MATCHERS = [
  (key: string) => key.startsWith('cache_dashboard_') && key !== CACHE_KEYS.dashboard,
  (key: string) => (
    key.startsWith('cache_etf_premium_history_')
    && !key.startsWith(CACHE_KEYS.historyPrefix)
  ),
]
const AUTO_REFRESH_INTERVAL_MS = 60 * 60 * 1000
const HISTORY_PREFETCH_CONCURRENCY = 2
const HISTORY_PREFETCH_DELAY_MS = 800

export const PREMIUM_CACHE_UPDATED_EVENT = 'premium-cache-updated'

let staleCacheCleared = false
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
let warmupPromise: Promise<void> | null = null
let refreshAllPromise: Promise<void> | null = null
let historyPrefetchTimer: ReturnType<typeof setTimeout> | null = null
let activeHistoryPrefetchCount = 0
let publicDataEnabled: boolean | null = null
const inFlight = new Map<string, Promise<unknown>>()
const historyPrefetchQueue: string[] = []
const queuedHistoryCodes = new Set<string>()

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

function clearStaleCacheOnce(): void {
  if (staleCacheCleared) return
  staleCacheCleared = true

  clearCacheKeys((key) => STALE_CACHE_MATCHERS.some((matches) => matches(key)))
}

function clearPremiumDataCache(): void {
  clearCacheKeys((key) => PREMIUM_CACHE_MATCHERS.some((matches) => matches(key)))
}

function publicDataDisabled(data: { data_enabled?: boolean }): boolean {
  return data.data_enabled === false
}

function markPublicDataDisabled(): void {
  publicDataEnabled = false
  clearHistoryPrefetchQueue()
  clearPremiumDataCache()
}

function markPublicDataEnabled(): void {
  publicDataEnabled = true
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

function historyRequestKey(code: string): string {
  return `history:${code}`
}

function historyCacheKey(code: string): string {
  return CACHE_KEYS.historyPrefix + code
}

function getCachedHistory(code: string): EtfPremiumHistory | null {
  if (DISABLE_CACHE) return null
  return getCache<EtfPremiumHistory>(historyCacheKey(code))
}

function setHistoryCache(code: string, data: EtfPremiumHistory): void {
  if (!DISABLE_CACHE && publicDataEnabled === true) {
    setCache(historyCacheKey(code), data)
  }
}

function fetchHistoryFromNetwork(code: string): Promise<EtfPremiumHistory> {
  return singleFlight(historyRequestKey(code), async () => {
    const data = await request<EtfPremiumHistory>(`/api/etfs/history?code=${encodeURIComponent(code)}`)
    if (publicDataDisabled(data)) {
      markPublicDataDisabled()
      return data
    }

    markPublicDataEnabled()
    setHistoryCache(code, data)
    return data
  })
}

function removeQueuedHistoryCode(code: string): void {
  if (!queuedHistoryCodes.delete(code)) return

  const index = historyPrefetchQueue.indexOf(code)
  if (index >= 0) {
    historyPrefetchQueue.splice(index, 1)
  }
}

function scheduleHistoryPrefetch(delayMs = HISTORY_PREFETCH_DELAY_MS): void {
  if (historyPrefetchTimer) return

  historyPrefetchTimer = setTimeout(() => {
    historyPrefetchTimer = null
    runHistoryPrefetchQueue()
  }, delayMs)
}

function runHistoryPrefetchQueue(): void {
  while (
    activeHistoryPrefetchCount < HISTORY_PREFETCH_CONCURRENCY
    && historyPrefetchQueue.length > 0
  ) {
    const code = historyPrefetchQueue.shift()!
    queuedHistoryCodes.delete(code)

    if (getCachedHistory(code) || inFlight.has(historyRequestKey(code))) {
      continue
    }

    activeHistoryPrefetchCount += 1
    fetchHistoryFromNetwork(code)
      .catch((err) => {
        logBackgroundError(`Failed to prefetch ETF premium history: ${code}`, err)
      })
      .finally(() => {
        activeHistoryPrefetchCount -= 1
        runHistoryPrefetchQueue()
      })
  }
}

function enqueueHistoryPrefetch(codes: string[]): void {
  if (USE_MOCK || DISABLE_CACHE) return
  clearStaleCacheOnce()

  let added = false
  codes.forEach((rawCode) => {
    const code = rawCode.trim()
    if (
      !code
      || queuedHistoryCodes.has(code)
      || getCachedHistory(code)
      || inFlight.has(historyRequestKey(code))
    ) {
      return
    }

    queuedHistoryCodes.add(code)
    historyPrefetchQueue.push(code)
    added = true
  })

  if (added) scheduleHistoryPrefetch()
}

function enqueueDashboardHistoryPrefetch(snapshot: DashboardSnapshot): void {
  enqueueHistoryPrefetch(snapshot.items.map((item) => item.code))
}

function clearHistoryPrefetchQueue(): void {
  if (historyPrefetchTimer) {
    clearTimeout(historyPrefetchTimer)
    historyPrefetchTimer = null
  }

  historyPrefetchQueue.splice(0)
  queuedHistoryCodes.clear()
}

function groupRangeSummary(
  items: DashboardItem[],
): Record<PremiumRange, { min_premium: number | null; max_premium: number | null }> {
  const ranges = {} as Record<PremiumRange, { min_premium: number | null; max_premium: number | null }>

  RANGE_OPTIONS.forEach(({ value }) => {
    const rates = items
      .map((item) => item.stats[value].latest?.premium_rate)
      .filter((rate): rate is number => typeof rate === 'number' && Number.isFinite(rate))

    ranges[value] = {
      min_premium: rates.length > 0 ? Math.min(...rates) : null,
      max_premium: rates.length > 0 ? Math.max(...rates) : null,
    }
  })

  return ranges
}

function toDashboardStats(stats: ReturnType<typeof summarizePremium>): DashboardStats {
  return {
    latest: stats.latest
      ? {
          date: stats.latest.date,
          premium_rate: stats.latest.premium_rate,
        }
      : null,
    percentile: stats.percentile,
    status: stats.status,
  }
}

function buildMockDashboard(): DashboardSnapshot {
  const list = mockEtfs as EtfInfo[]
  const items = list.map<DashboardItem>((info) => {
    const history = mockHistoryFor(info.code)
    const data = history.data.length > 0 ? history.data : (info.latest ? [info.latest] : [])
    const stats = RANGE_OPTIONS.reduce((acc, option) => {
      acc[option.value] = toDashboardStats(summarizePremium(data, option.value))
      return acc
    }, {} as Record<PremiumRange, DashboardStats>)

    return {
      code: info.code,
      name: history.name || info.name,
      short_name: history.short_name || info.short_name,
      stats,
    }
  })

  const itemByCode = Object.fromEntries(items.map((item) => [item.code, item]))
  const groupsByKey = new Map<string, DashboardGroup>()
  const order: string[] = []

  list.forEach((info) => {
    const key = info.tracking_index || '__UNGROUPED__'
    let group = groupsByKey.get(key)
    if (!group) {
      group = {
        tracking_index: key,
        tracking_index_name: info.tracking_index_name || '未分类',
        members: [],
        ranges: {} as DashboardGroup['ranges'],
      }
      groupsByKey.set(key, group)
      order.push(key)
    }
    group.members.push(info.code)
  })

  groupsByKey.forEach((group) => {
    group.ranges = groupRangeSummary(
      group.members
        .map((code) => itemByCode[code])
        .filter((item): item is DashboardItem => !!item),
    )
  })

  return {
    data_enabled: true,
    items,
    groups: order.map((key) => groupsByKey.get(key)!).filter(Boolean),
  }
}

export async function fetchDashboard(forceRefresh = false): Promise<DashboardSnapshot> {
  if (USE_MOCK) return buildMockDashboard()
  clearStaleCacheOnce()

  if (!forceRefresh && !DISABLE_CACHE) {
    const cached = getCache<DashboardSnapshot>(CACHE_KEYS.dashboard)
    if (cached) {
      enqueueDashboardHistoryPrefetch(cached)
      return cached
    }
  }

  return singleFlight('dashboard', async () => {
    const data = await request<DashboardSnapshot>('/api/dashboard')
    if (publicDataDisabled(data)) {
      markPublicDataDisabled()
      return data
    }

    markPublicDataEnabled()
    if (!DISABLE_CACHE) setCache(CACHE_KEYS.dashboard, data)
    enqueueDashboardHistoryPrefetch(data)
    return data
  }).catch(() => {
    throw new Error('首页数据加载失败')
  })
}

export async function fetchPremiumHistory(
  code: string,
  forceRefresh = false,
): Promise<EtfPremiumHistory> {
  const normalizedCode = code.trim()
  if (!normalizedCode) throw new Error('ETF 代码无效')

  if (USE_MOCK) return mockHistoryFor(normalizedCode)
  clearStaleCacheOnce()

  if (!forceRefresh && !DISABLE_CACHE) {
    const cached = getCachedHistory(normalizedCode)
    if (cached) return cached
  }

  removeQueuedHistoryCode(normalizedCode)

  return fetchHistoryFromNetwork(normalizedCode).catch(() => {
    throw new Error(`${normalizedCode} 溢价历史加载失败`)
  })
}

export function warmPremiumCache(): void {
  if (USE_MOCK || warmupPromise) return

  warmupPromise = (async () => {
    await fetchDashboard(false)
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
    await fetchDashboard(true)
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
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
  clearHistoryPrefetchQueue()
}
