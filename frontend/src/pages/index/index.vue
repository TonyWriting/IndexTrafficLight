<template>
  <view class="dashboard">
    <view class="range-tabs">
      <view
        v-for="option in RANGE_OPTIONS"
        :key="option.value"
        class="range-tab"
        :class="{ active: selectedRange === option.value }"
        @click="selectedRange = option.value"
      >
        <text>{{ option.label }}</text>
      </view>
    </view>

    <view v-if="loading" class="state-panel">
      <text>加载中...</text>
    </view>

    <view v-else-if="error" class="state-panel">
      <text class="state-error">{{ error }}</text>
      <view class="state-action" @click="loadData(true)">
        <text>重试</text>
      </view>
    </view>

    <view v-else-if="dashboardGroups.length === 0" class="state-panel">
      <text>暂无数据</text>
    </view>

    <view v-else class="card-list">
      <view
        v-for="group in dashboardGroups"
        :key="group.tracking_index"
        class="group-frame"
      >
        <EtfGroupHeader
          :tracking-index-name="group.tracking_index_name"
          :member-count="group.members.length"
          :min-premium="group.min_premium"
          :max-premium="group.max_premium"
        />
        <view class="group-body">
          <view v-if="group.members.length >= 2" class="tile-grid">
            <EtfMiniTile
              v-for="item in group.members"
              :key="item.info.code"
              :code="item.info.code"
              :name="item.info.short_name || item.info.name || item.info.code"
              :latest="item.stats.latest"
              :percentile="item.stats.percentile"
              :status="item.stats.status"
              @click="openDetail"
            />
          </view>
          <EtfCard
            v-for="item in group.members"
            v-else
            :key="item.info.code"
            :code="item.info.code"
            :name="item.displayName"
            :latest="item.stats.latest"
            :percentile="item.stats.percentile"
            :status="item.stats.status"
            @click="openDetail"
          />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import EtfCard from '../../components/EtfCard.vue'
import EtfGroupHeader from '../../components/EtfGroupHeader.vue'
import EtfMiniTile from '../../components/EtfMiniTile.vue'
import { fetchEtfs, fetchPremiumHistory, PREMIUM_CACHE_UPDATED_EVENT } from '../../api'
import type { EtfInfo, EtfPremiumHistory, PremiumRange, PremiumStats } from '../../types'
import { RANGE_OPTIONS } from '../../types'
import { summarizePremium } from '../../utils/premium'

interface DashboardItem {
  info: EtfInfo
  displayName: string
  stats: PremiumStats
}

interface DashboardGroup {
  tracking_index: string
  tracking_index_name: string
  members: DashboardItem[]
  min_premium: number | null
  max_premium: number | null
}

const FALLBACK_INDEX_KEY = '__UNGROUPED__'
const FALLBACK_INDEX_NAME = '未分类'

const loading = ref(true)
const error = ref('')
const etfs = ref<EtfInfo[]>([])
const histories = ref<Record<string, EtfPremiumHistory>>({})
const selectedRange = ref<PremiumRange>('1y')

const dashboardItems = computed<DashboardItem[]>(() => (
  etfs.value
    .map((info) => {
      const history = histories.value[info.code]
      const fallback = info.latest ? [info.latest] : []
      return {
        info,
        displayName: history?.short_name || history?.name || info.short_name || info.name || info.code,
        stats: summarizePremium(history?.data || fallback, selectedRange.value),
      }
    })
    .filter((item) => item.stats.latest)
))

const dashboardGroups = computed<DashboardGroup[]>(() => {
  const order: string[] = []
  const groups = new Map<string, DashboardGroup>()

  for (const item of dashboardItems.value) {
    const key = item.info.tracking_index || FALLBACK_INDEX_KEY
    const name = item.info.tracking_index_name || FALLBACK_INDEX_NAME

    let group = groups.get(key)
    if (!group) {
      group = {
        tracking_index: key,
        tracking_index_name: name,
        members: [],
        min_premium: null,
        max_premium: null,
      }
      groups.set(key, group)
      order.push(key)
    }
    group.members.push(item)
  }

  for (const group of groups.values()) {
    group.members.sort((a, b) => {
      const pa = a.stats.latest?.premium_rate ?? Number.POSITIVE_INFINITY
      const pb = b.stats.latest?.premium_rate ?? Number.POSITIVE_INFINITY
      return pa - pb
    })

    const rates = group.members
      .map((member) => member.stats.latest?.premium_rate)
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))

    if (rates.length > 0) {
      group.min_premium = Math.min(...rates)
      group.max_premium = Math.max(...rates)
    }
  }

  return order.map((key) => groups.get(key)!).filter(Boolean)
})

async function loadData(forceRefresh = false, silent = false) {
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    const list = await fetchEtfs(forceRefresh)
    const historyPairs = await Promise.all(
      list.map(async (info) => [info.code, await fetchPremiumHistory(info.code, forceRefresh)] as const),
    )

    etfs.value = list
    histories.value = Object.fromEntries(historyPairs)
    error.value = ''
  } catch (err: any) {
    if (!silent) {
      error.value = err?.message || '数据加载失败'
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

function openDetail(code: string) {
  uni.navigateTo({ url: `/pages/detail/detail?code=${encodeURIComponent(code)}` })
}

function handlePremiumCacheUpdated() {
  if (!loading.value) {
    void loadData(false, true)
  }
}

onMounted(() => {
  uni.$on(PREMIUM_CACHE_UPDATED_EVENT, handlePremiumCacheUpdated)
  loadData()
})

onUnmounted(() => {
  uni.$off(PREMIUM_CACHE_UPDATED_EVENT, handlePremiumCacheUpdated)
})

onPullDownRefresh(async () => {
  await loadData(true)
  uni.stopPullDownRefresh()
})
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  padding: 28rpx 24rpx 40rpx;
  background: #f1f5f9;
}

.range-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8rpx;
  margin: 0 0 22rpx;
  padding: 6rpx;
  background: #e2e8f0;
  border-radius: 14rpx;
}

.range-tab {
  min-height: 62rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10rpx;
}

.range-tab text {
  color: #475569;
  font-size: 24rpx;
  font-weight: 700;
}

.range-tab.active {
  background: #ffffff;
  box-shadow: 0 3rpx 10rpx rgba(15, 23, 42, 0.08);
}

.range-tab.active text {
  color: #0f172a;
}

.state-panel {
  min-height: 260rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20rpx;
  color: #64748b;
  font-size: 26rpx;
}

.state-error {
  color: #b91c1c;
}

.state-action {
  padding: 12rpx 34rpx;
  background: #2563eb;
  border-radius: 10rpx;
}

.state-action text {
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 700;
}

.card-list {
  margin-top: 4rpx;
}

.group-frame {
  margin-bottom: 24rpx;
  background: #ffffff;
  border: 2rpx solid #cbd5e1;
  border-radius: 18rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 14rpx rgba(15, 23, 42, 0.05);
}

.group-body {
  padding: 18rpx;
}

.tile-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12rpx;
}

.group-body :deep(.etf-card) {
  margin-bottom: 0;
  box-shadow: none;
}
</style>
