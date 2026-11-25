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
            <text class="fund-code" selectable>{{ codeLine }}</text>
          </view>
          <view class="status-badge" :style="{ backgroundColor: statusConfig.bgColor }">
            <text class="status-text" :style="{ color: statusConfig.color }" selectable>
              {{ statusConfig.label }}
            </text>
          </view>
        </view>

        <view class="summary-main">
          <view>
            <text class="metric-label">溢价率</text>
            <text class="premium-value" :style="{ color: statusConfig.color }" selectable>
              {{ formatPremiumRate(stats.latest.premium_rate) }}
            </text>
          </view>
          <view class="rank-box">
            <text class="rank-value" selectable>P{{ percentileLabel }}</text>
            <text class="metric-label">历史分位</text>
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
        v-if="!explainSheetOpen"
        :records="history?.data || []"
        :range="selectedRange"
        :stats="stats"
        canvas-id="premiumDetailChart"
      />

      <view class="explain-panel">
        <view class="explain-head">
          <view class="explain-icon">
            <text>i</text>
          </view>
          <text class="explain-title">溢价率怎么看？</text>
        </view>
        <text class="explain-body collapsed">
          {{ explainSummary }}
        </text>
        <view class="explain-more" @click="explainSheetOpen = true">
          <text>更多</text>
          <view class="more-chevron" />
        </view>
      </view>

      <view v-if="explainSheetOpen" class="sheet-mask" @click="explainSheetOpen = false">
        <view class="explain-sheet" @click.stop>
          <view class="sheet-head">
            <text class="sheet-title" selectable user-select>溢价率怎么看？</text>
            <view class="sheet-close" @click.stop="explainSheetOpen = false">x</view>
          </view>
          <scroll-view class="explain-sheet-scroll" scroll-y>
            <view class="sheet-section">
              <text class="sheet-section-title" selectable user-select>1. 什么是溢价率</text>
              <text
                v-for="paragraph in premiumDefinitionParagraphs"
                :key="paragraph"
                class="sheet-paragraph"
                selectable
                user-select
              >
                {{ paragraph }}
              </text>
            </view>

            <view class="sheet-section">
              <text class="sheet-section-title" selectable user-select>2. 溢价率高低怎么看</text>
              <text class="sheet-paragraph" selectable user-select>{{ premiumLevelIntro }}</text>
              <view class="level-row">
                <text class="level-label level-extreme" selectable user-select>过高</text>
                <text class="level-detail" selectable user-select>历史分位 P90 或以上</text>
              </view>
              <view class="level-row">
                <text class="level-label level-above-normal" selectable user-select>偏高</text>
                <text class="level-detail" selectable user-select>历史分位 P70（含）至 P90（不含）</text>
              </view>
              <view class="level-row">
                <text class="level-label level-normal" selectable user-select>中游</text>
                <text class="level-detail" selectable user-select>历史分位 P30（含）至 P70（不含）</text>
              </view>
              <view class="level-row">
                <text class="level-label level-below-normal" selectable user-select>偏低</text>
                <text class="level-detail" selectable user-select>历史分位 P10（含）至 P30（不含）</text>
              </view>
              <view class="level-row">
                <text class="level-label level-low" selectable user-select>过低</text>
                <text class="level-detail" selectable user-select>历史分位低于 P10</text>
              </view>
            </view>

            <view class="sheet-section sheet-disclaimer-section">
              <text
                v-for="(paragraph, index) in disclaimerParagraphs"
                :key="paragraph"
                class="sheet-disclaimer"
                selectable
                user-select
              ><text v-if="index === 0">免责说明：</text>{{ paragraph }}</text>
            </view>
          </scroll-view>
        </view>
      </view>

    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { onHide, onLoad, onShareAppMessage, onShareTimeline, onShow, onUnload } from '@dcloudio/uni-app'
import PremiumChart from '../../components/PremiumChart.vue'
import {
  fetchPremiumHistory,
  fetchReviewMode,
  PREMIUM_CACHE_UPDATED_EVENT,
  startPremiumAutoRefresh,
  stopPremiumAutoRefresh,
} from '../../api'
import type { EtfPremiumHistory, PremiumRange } from '../../types'
import {
  PREMIUM_STATUS_CONFIG,
  RANGE_OPTIONS,
} from '../../types'
import {
  formatPremiumRate,
  formatShortDate,
  summarizePremium,
} from '../../utils/premium'

const code = ref('159509')
const loading = ref(true)
const error = ref('')
const history = ref<EtfPremiumHistory | null>(null)
const selectedRange = ref<PremiumRange>('3m')
const explainSheetOpen = ref(false)
let pageVisible = false

const explainSummary = '优先使用当天采集的 IOPV；缺少时使用同一天的净值模拟记录，复盘场内收盘溢价。'
const premiumDefinitionParagraphs = [
  '溢价率 = 场内收盘价 ÷ 参考净值 − 1。正数是溢价，负数是折价。',
  '同一交易日有有效 IOPV 时优先使用，并采用同次采集的成交价；没有时使用该交易日已保存的净值模拟记录。两者都没有就跳过。',
  '净值模拟采用 A 股开盘前最近一次美股收盘对应日期的正式净值。',
]
const premiumLevelIntro = '历史分位表示本次溢价率在所选区间中的位置：分位越高，溢价越高。'
const disclaimerParagraphs = [
  '本项目为个人维护的数据整理与展示工具，基于公开信息和本项目计算逻辑生成，不保证数据的准确性、完整性和及时性。内容仅供学习研究和信息参考，不构成任何投资建议，也不应作为买入或卖出依据。实际决策前请自行核验数据并阅读基金相关法律文件，市场有风险，投资需谨慎。',
]

const stats = computed(() => summarizePremium(history.value?.data || [], selectedRange.value))
const statusConfig = computed(() => PREMIUM_STATUS_CONFIG[stats.value.status])
const displayName = computed(() => history.value?.short_name || history.value?.name || code.value)
const codeLine = computed(() => {
  const date = stats.value.latest?.date
  return date ? `${code.value} · ${formatShortDate(date)}` : code.value
})

const percentileLabel = computed(() => {
  const value = stats.value.percentile
  if (!Number.isFinite(value)) return '--'
  return Math.round(value * 100).toString()
})

const statCards = computed(() => [
  { label: '平均值', value: formatPremiumRate(stats.value.mean) },
  { label: '中位数', value: formatPremiumRate(stats.value.median) },
])

async function loadData(forceRefresh = false, silent = false) {
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    if (await fetchReviewMode()) {
      closeUnavailableDetail()
      return
    }

    applyHistory(await fetchPremiumHistory(code.value, forceRefresh))
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

function applyHistory(data: EtfPremiumHistory): void {
  history.value = data
  if (pageVisible) {
    uni.setNavigationBarTitle({
      title: history.value.short_name || code.value,
    })
    startPremiumAutoRefresh()
  }
  error.value = ''
}

function closeUnavailableDetail() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack({ delta: 1 })
  } else {
    uni.redirectTo({ url: '/pages/index/index' })
  }
}

function handlePremiumCacheUpdated() {
  if (pageVisible && !loading.value) {
    void loadData(false, true)
  }
}

onLoad((query: Record<string, string | undefined> = {}) => {
  code.value = query.code || '159509'
})

onShow(() => {
  pageVisible = true
  void loadData(false, history.value !== null)
})

function stopPageRefresh(): void {
  if (!pageVisible) return
  pageVisible = false
  stopPremiumAutoRefresh()
}

onHide(stopPageRefresh)
onUnload(stopPageRefresh)

onMounted(() => {
  uni.$on(PREMIUM_CACHE_UPDATED_EVENT, handlePremiumCacheUpdated)
})

onUnmounted(() => {
  uni.$off(PREMIUM_CACHE_UPDATED_EVENT, handlePremiumCacheUpdated)
})

function shareTitle(): string {
  const latest = stats.value.latest
  return latest
    ? `${displayName.value} 溢价率 ${formatPremiumRate(latest.premium_rate)}`
    : `${displayName.value} 溢价率走势`
}

onShareAppMessage(() => ({
  title: shareTitle(),
  path: `/pages/detail/detail?code=${encodeURIComponent(code.value)}`,
}))

onShareTimeline(() => ({
  title: shareTitle(),
  query: `code=${encodeURIComponent(code.value)}`,
}))
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

.stat-cell {
  min-width: 0;
  background: #f8fafc;
  border-radius: 12rpx;
  padding: 14rpx 16rpx;
}

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
  grid-template-columns: repeat(3, 1fr);
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

.explain-panel {
  margin-top: 20rpx;
  background: #ffffff;
  border: 1rpx solid #e2e8f0;
  border-radius: 16rpx;
  padding: 24rpx;
}

.explain-head {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 12rpx;
}

.explain-icon {
  flex-shrink: 0;
  width: 34rpx;
  height: 34rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fef3c7;
  border: 1rpx solid #fcd34d;
  border-radius: 999rpx;
}

.explain-icon text {
  color: #92400e;
  font-size: 22rpx;
  font-weight: 800;
  line-height: 34rpx;
}

.explain-title {
  color: #0f172a;
  font-size: 28rpx;
  font-weight: 800;
  line-height: 36rpx;
}

.explain-body {
  display: block;
  color: #475569;
  font-size: 24rpx;
  line-height: 38rpx;
}

.explain-body.collapsed {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.explain-more {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-top: 8rpx;
}

.explain-more text {
  color: #c2410c;
  font-size: 24rpx;
  font-weight: 700;
  line-height: 34rpx;
}

.more-chevron {
  width: 11rpx;
  height: 11rpx;
  margin-left: 5rpx;
  border-top: 3rpx solid #c2410c;
  border-right: 3rpx solid #c2410c;
  transform: translateY(-2rpx) rotate(45deg);
  box-sizing: border-box;
}

.sheet-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-end;
  background: rgba(15, 23, 42, 0.48);
}

.explain-sheet {
  width: 100%;
  height: 78vh;
  background: #ffffff;
  border-radius: 32rpx 32rpx 0 0;
  padding: 28rpx 32rpx 34rpx;
  box-sizing: border-box;
}

.sheet-head {
  position: relative;
  min-height: 52rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18rpx;
}

.sheet-title {
  color: #0f172a;
  font-size: 34rpx;
  font-weight: 800;
  line-height: 46rpx;
}

.sheet-close {
  position: absolute;
  right: -10rpx;
  top: -4rpx;
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 42rpx;
  font-weight: 300;
  line-height: 64rpx;
  text-align: center;
}

.explain-sheet-scroll {
  height: calc(78vh - 132rpx);
  box-sizing: border-box;
}

.sheet-section {
  margin-top: 28rpx;
}

.sheet-section:first-child {
  margin-top: 0;
}

.sheet-section-title {
  display: block;
  color: #111827;
  font-size: 29rpx;
  font-weight: 800;
  line-height: 38rpx;
}

.sheet-paragraph {
  display: block;
  margin-top: 10rpx;
  color: #111827;
  font-size: 26rpx;
  line-height: 40rpx;
  white-space: normal;
}

.level-row {
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
  margin-top: 8rpx;
}

.level-label {
  flex-shrink: 0;
  width: 64rpx;
  font-size: 25rpx;
  font-weight: 650;
  line-height: 36rpx;
}

.level-label.level-extreme {
  color: #dc2626;
}

.level-label.level-above-normal {
  color: #ea580c;
}

.level-label.level-normal {
  color: #d97706;
}

.level-label.level-below-normal {
  color: #22c55e;
}

.level-label.level-low {
  color: #10b981;
}

.level-detail {
  min-width: 0;
  flex: 1;
  color: #334155;
  font-size: 25rpx;
  line-height: 36rpx;
}

.sheet-disclaimer-section {
  margin-top: 32rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid #e2e8f0;
}

.sheet-disclaimer {
  display: block;
  margin-top: 8rpx;
  color: #94a3b8;
  font-size: 22rpx;
  line-height: 32rpx;
  white-space: normal;
}

.sheet-disclaimer:first-child {
  margin-top: 0;
}

</style>
