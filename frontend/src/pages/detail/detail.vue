<template>
  <view class="detail-page">
    <view v-if="loading" class="state-panel">
      <text>加载中...</text>
    </view>

    <view v-else-if="error" class="state-panel">
      <text class="state-error">{{ error }}</text>
      <view class="state-action" @click="loadData(true)">
        <text>重试</text>
      </view>
    </view>

    <view v-else-if="!stats.latest" class="state-panel">
      <text>暂无数据</text>
    </view>

    <view v-else class="content">
      <view class="summary-panel" :style="{ borderColor: statusConfig.borderColor }">
        <view class="summary-head">
          <view class="title-block">
            <text class="fund-name" selectable>{{ displayName }}</text>
            <text class="fund-code" selectable>{{ code }}</text>
          </view>
          <view class="status-badge" :style="{ backgroundColor: statusConfig.bgColor }">
            <text class="status-text" :style="{ color: statusConfig.color }" selectable>
              {{ statusConfig.label }}
            </text>
          </view>
        </view>

        <view class="summary-main">
          <view>
            <text class="metric-label">当前溢价</text>
            <text class="premium-value" :style="{ color: statusConfig.color }" selectable>
              {{ formatPremiumRate(stats.latest.premium_rate) }}
            </text>
          </view>
          <view class="rank-box">
            <text class="rank-value" selectable>P{{ percentileLabel }}</text>
            <text class="metric-label">历史分位</text>
          </view>
        </view>

        <view class="quote-row">
          <view class="quote-item">
            <text class="quote-label">收盘价</text>
            <text class="quote-value" selectable>{{ formatPrice(stats.latest.close) }}</text>
          </view>
          <view class="quote-item">
            <text class="quote-label">基金净值</text>
            <text class="quote-value" selectable>{{ formatPrice(stats.latest.nav) }}</text>
          </view>
          <view class="quote-item">
            <text class="quote-label">日期</text>
            <text class="quote-value" selectable>{{ formatShortDate(stats.latest.date) }}</text>
          </view>
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

      <view class="stats-grid">
        <view v-for="item in statCards" :key="item.label" class="stat-cell">
          <text class="stat-label">{{ item.label }}</text>
          <text class="stat-value" selectable>{{ item.value }}</text>
        </view>
      </view>

      <PremiumChart
        :records="history?.data || []"
        :range="selectedRange"
        :stats="stats"
        canvas-id="premiumDetailChart"
      />

      <view class="recent-panel">
        <view class="section-head">
          <text class="section-title">最近记录</text>
          <text class="section-meta">{{ recentRows.length }} 条</text>
        </view>

        <view class="table-head">
          <text class="col date">日期</text>
          <text class="col">收盘</text>
          <text class="col">基金净值</text>
          <text class="col premium">溢价</text>
        </view>

        <view v-for="record in recentRows" :key="record.date" class="table-row">
          <text class="col date" selectable>{{ formatShortDate(record.date) }}</text>
          <text class="col" selectable>{{ formatPrice(record.close) }}</text>
          <text class="col" selectable>{{ formatPrice(record.nav) }}</text>
          <text class="col premium" selectable>{{ formatPremiumRate(record.premium_rate) }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import PremiumChart from '../../components/PremiumChart.vue'
import { fetchPremiumHistory, PREMIUM_CACHE_UPDATED_EVENT } from '../../api'
import type { EtfPremiumHistory, PremiumRange } from '../../types'
import { PREMIUM_STATUS_CONFIG, RANGE_OPTIONS } from '../../types'
import {
  filterByRange,
  formatPremiumRate,
  formatPrice,
  formatShortDate,
  summarizePremium,
} from '../../utils/premium'

const code = ref('159509')
const loading = ref(true)
const error = ref('')
const history = ref<EtfPremiumHistory | null>(null)
const selectedRange = ref<PremiumRange>('1y')

const stats = computed(() => summarizePremium(history.value?.data || [], selectedRange.value))
const statusConfig = computed(() => PREMIUM_STATUS_CONFIG[stats.value.status])
const displayName = computed(() => history.value?.short_name || history.value?.name || code.value)

const percentileLabel = computed(() => {
  const value = stats.value.percentile
  if (!Number.isFinite(value)) return '--'
  return Math.round(value * 100).toString()
})

const statCards = computed(() => [
  { label: '平均溢价', value: formatPremiumRate(stats.value.mean) },
  { label: '中位数', value: formatPremiumRate(stats.value.median) },
])

const recentRows = computed(() => (
  filterByRange(history.value?.data || [], selectedRange.value)
    .slice(-8)
    .reverse()
))

async function loadData(forceRefresh = false, silent = false) {
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    history.value = await fetchPremiumHistory(code.value, forceRefresh)
    uni.setNavigationBarTitle({ title: history.value.short_name || code.value })
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

function handlePremiumCacheUpdated() {
  if (!loading.value) {
    void loadData(false, true)
  }
}

onLoad((query: Record<string, string | undefined> = {}) => {
  code.value = query.code || '159509'
  loadData()
})

onMounted(() => {
  uni.$on(PREMIUM_CACHE_UPDATED_EVENT, handlePremiumCacheUpdated)
})

onUnmounted(() => {
  uni.$off(PREMIUM_CACHE_UPDATED_EVENT, handlePremiumCacheUpdated)
})
</script>

<style scoped>
.detail-page {
  min-height: 100vh;
  padding: 24rpx;
  background: #f1f5f9;
}

.content {
  padding-bottom: 40rpx;
}

.state-panel {
  min-height: 420rpx;
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

.summary-panel {
  background: #ffffff;
  border: 2rpx solid;
  border-radius: 16rpx;
  padding: 28rpx;
  box-shadow: 0 6rpx 20rpx rgba(15, 23, 42, 0.06);
}

.summary-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
}

.title-block {
  min-width: 0;
  flex: 1;
}

.fund-name {
  display: block;
  color: #0f172a;
  font-size: 34rpx;
  font-weight: 800;
  line-height: 44rpx;
}

.fund-code {
  display: block;
  margin-top: 4rpx;
  color: #64748b;
  font-size: 22rpx;
  line-height: 30rpx;
}

.status-badge {
  flex-shrink: 0;
  border-radius: 8rpx;
  padding: 8rpx 14rpx;
}

.status-text {
  font-size: 22rpx;
  font-weight: 700;
  line-height: 28rpx;
}

.summary-main {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
  margin-top: 32rpx;
}

.metric-label,
.quote-label,
.stat-label {
  display: block;
  color: #64748b;
  font-size: 22rpx;
  line-height: 30rpx;
}

.premium-value {
  display: block;
  margin-top: 4rpx;
  font-size: 54rpx;
  font-weight: 800;
  line-height: 64rpx;
}

.rank-box {
  text-align: right;
}

.rank-value {
  display: block;
  color: #0f172a;
  font-size: 36rpx;
  font-weight: 800;
  line-height: 46rpx;
}

.quote-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
  margin-top: 26rpx;
}

.quote-item,
.stat-cell {
  min-width: 0;
  background: #f8fafc;
  border-radius: 12rpx;
  padding: 14rpx 16rpx;
}

.quote-value,
.stat-value {
  display: block;
  margin-top: 2rpx;
  color: #0f172a;
  font-size: 25rpx;
  font-weight: 700;
  line-height: 34rpx;
}

.range-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8rpx;
  margin: 22rpx 0;
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14rpx;
}

.recent-panel {
  margin-top: 20rpx;
  background: #ffffff;
  border: 1rpx solid #e2e8f0;
  border-radius: 16rpx;
  padding: 24rpx;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 16rpx;
}

.section-title {
  color: #0f172a;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 38rpx;
}

.section-meta {
  color: #64748b;
  font-size: 22rpx;
  line-height: 30rpx;
}

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr 1.2fr;
  gap: 10rpx;
  align-items: center;
  min-height: 56rpx;
}

.table-head {
  border-bottom: 1rpx solid #e2e8f0;
}

.table-row {
  border-bottom: 1rpx solid #f1f5f9;
}

.table-row:last-child {
  border-bottom: 0;
}

.col {
  color: #0f172a;
  font-size: 22rpx;
  line-height: 30rpx;
  text-align: right;
}

.table-head .col {
  color: #64748b;
  font-weight: 700;
}

.col.date {
  text-align: left;
}

.col.premium {
  font-weight: 800;
}
</style>
