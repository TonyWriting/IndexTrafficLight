<template>
  <view class="dashboard">
    <view class="topbar">
      <view class="title-block">
        <text class="page-title">QDII ETF 溢价灯</text>
        <text class="page-subtitle">盘后数据 · {{ latestDateText }}</text>
      </view>
      <view class="refresh-btn" @click="loadData(true)">
        <text>刷新</text>
      </view>
    </view>

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

    <view v-else-if="dashboardItems.length === 0" class="state-panel">
      <text>暂无数据</text>
    </view>

    <view v-else class="card-list">
      <EtfCard
        v-for="item in dashboardItems"
        :key="item.info.code"
        :code="item.info.code"
        :name="item.displayName"
        :latest="item.stats.latest"
        :percentile="item.stats.percentile"
        :status="item.stats.status"
        :mean="item.stats.mean"
        :median="item.stats.median"
        @click="openDetail"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import EtfCard from '../../components/EtfCard.vue'
import { fetchEtfs, fetchPremiumHistory, PREMIUM_CACHE_UPDATED_EVENT } from '../../api'
import type { EtfInfo, EtfPremiumHistory, PremiumRange } from '../../types'
import { RANGE_OPTIONS } from '../../types'
import { summarizePremium } from '../../utils/premium'

const loading = ref(true)
const error = ref('')
const etfs = ref<EtfInfo[]>([])
const histories = ref<Record<string, EtfPremiumHistory>>({})
const selectedRange = ref<PremiumRange>('all')

const dashboardItems = computed(() => (
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

const latestDateText = computed(() => {
  const dates = dashboardItems.value
    .map((item) => item.stats.latest?.date || '')
    .filter(Boolean)
    .sort()
  return dates[dates.length - 1] || '--'
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

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
}

.title-block {
  min-width: 0;
}

.page-title {
  display: block;
  color: #0f172a;
  font-size: 40rpx;
  font-weight: 800;
  line-height: 50rpx;
}

.page-subtitle {
  display: block;
  margin-top: 6rpx;
  color: #64748b;
  font-size: 22rpx;
  line-height: 30rpx;
}

.refresh-btn {
  flex-shrink: 0;
  padding: 12rpx 22rpx;
  background: #0f172a;
  border-radius: 10rpx;
}

.refresh-btn text {
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 700;
  line-height: 30rpx;
}

.range-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8rpx;
  margin: 28rpx 0 22rpx;
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
</style>
