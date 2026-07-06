<template>
  <view class="dashboard">
    <view
      v-if="!loading && !error && !dataUpdating && dashboardGroups.length > 0"
      class="range-tabs"
    >
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

    <view v-else-if="dataUpdating" class="state-panel">
      <text>{{ dashboard?.message || '数据更新中' }}</text>
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
          :min-status="group.min_status"
          :max-status="group.max_status"
        />
        <view class="group-body">
          <view v-if="group.members.length >= 2" class="tile-grid">
            <EtfMiniTile
              v-for="item in group.members"
              :key="item.code"
              :code="item.code"
              :name="item.displayName"
              :latest="item.stats.latest"
              :percentile="item.stats.percentile"
              :status="item.stats.status"
              @click="openDetail"
            />
          </view>
          <EtfCard
            v-for="item in group.members"
            v-else
            :key="item.code"
            :code="item.code"
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
import { onPullDownRefresh, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import EtfCard from '../../components/EtfCard.vue'
import EtfGroupHeader from '../../components/EtfGroupHeader.vue'
import EtfMiniTile from '../../components/EtfMiniTile.vue'
import { fetchDashboard, PREMIUM_CACHE_UPDATED_EVENT } from '../../api'
import type { DashboardSnapshot, DashboardStats, PremiumRange, PremiumStatus } from '../../types'
import { RANGE_OPTIONS } from '../../types'

interface DashboardItem {
  code: string
  displayName: string
  stats: DashboardStats
}

interface DashboardGroup {
  tracking_index: string
  tracking_index_name: string
  members: DashboardItem[]
  min_premium: number | null
  max_premium: number | null
  min_status: PremiumStatus | null
  max_status: PremiumStatus | null
}

const loading = ref(true)
const error = ref('')
const dashboard = ref<DashboardSnapshot | null>(null)
const selectedRange = ref<PremiumRange>('3m')
const dataUpdating = computed(() => dashboard.value?.data_enabled === false)

const dashboardGroups = computed<DashboardGroup[]>(() => {
  const snapshot = dashboard.value
  if (!snapshot) return []

  const itemByCode = new Map(snapshot.items.map((item) => [item.code, item]))

  return snapshot.groups
    .map((group) => {
      const members = group.members
        .map((code) => itemByCode.get(code))
        .filter((item): item is NonNullable<typeof item> => !!item)
        .map((item) => ({
          code: item.code,
          displayName: item.short_name || item.name || item.code,
          stats: item.stats[selectedRange.value],
        }))
        .filter((item) => item.stats.latest)

      members.sort((a, b) => {
        const pa = a.stats.latest?.premium_rate ?? Number.POSITIVE_INFINITY
        const pb = b.stats.latest?.premium_rate ?? Number.POSITIVE_INFINITY
        return pa - pb
      })

      const range = group.ranges[selectedRange.value]
      const minMember = members[0]
      const maxMember = members[members.length - 1]

      return {
        tracking_index: group.tracking_index,
        tracking_index_name: group.tracking_index_name,
        members,
        min_premium: range.min_premium,
        max_premium: range.max_premium,
        min_status: minMember?.stats.status ?? null,
        max_status: maxMember?.stats.status ?? null,
      }
    })
    .filter((group) => group.members.length > 0)
})

async function loadData(forceRefresh = false, silent = false) {
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    dashboard.value = await fetchDashboard(forceRefresh)
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

const SHARE_TITLE = 'QDII ETF 溢价灯 · 盘后看场内价格贵不贵'

onShareAppMessage(() => ({
  title: SHARE_TITLE,
  path: '/pages/index/index',
}))

onShareTimeline(() => ({
  title: SHARE_TITLE,
}))
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  padding: 28rpx 24rpx 40rpx;
  background: #f1f5f9;
}

.range-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
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
