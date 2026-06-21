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
            <text class="metric-label">当前溢价率</text>
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
            <text class="quote-label">场内收盘价</text>
            <text class="quote-value" selectable>{{ formatPrice(stats.latest.close) }}</text>
          </view>
          <view class="quote-item">
            <text class="quote-label">基金净值 NAV</text>
            <text class="quote-value" selectable>{{ formatPrice(stats.latest.nav) }}</text>
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
              <view
                v-for="item in explainLevelItems"
                :key="item.label"
                class="level-row"
              >
                <text class="level-label" selectable user-select>{{ item.label }}</text>
                <text class="level-detail" selectable user-select>{{ item.detail }}</text>
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

      <view class="recent-panel">
        <view class="section-head">
          <text class="section-title">最近记录</text>
        </view>

        <view class="table-head">
          <text class="col date">日期</text>
          <text class="col">场内收盘价</text>
          <text class="col">基金净值 NAV</text>
          <text class="col premium">溢价率</text>
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
import { onLoad, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
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
const explainSheetOpen = ref(false)

const explainSummary = 'ETF 的场内交易价格和基金净值不是一回事。溢价率看的是：场内价格相对基金净值多贵或便宜多少。'
const premiumDefinitionParagraphs = [
  'ETF 有两个价格：场内交易价格由买卖报价实时决定，基金净值 NAV 则按每个净值日，根据基金持有的一篮子资产、汇率和费用等计算得出。溢价率比较的是：场内收盘价相对基金净值贵了多少或便宜多少。',
  '用于比较的基金净值口径有两类：盘中参考净值 IOPV，和收盘后确认的正式净值 NAV。本页使用 NAV 口径：收盘溢价率 = 场内收盘价 / 当日 NAV - 1。正数是溢价，负数是折价。',
  'IOPV 是盘中的基金份额参考净值。同花顺等 App 里盘中看到的实时溢价率，通常更接近 IOPV 口径：拿最新的场内交易价格和盘中参考净值比较，用来辅助盘中交易。',
  'QDII ETF 跟踪海外资产，A 股交易时海外市场可能没开盘，IOPV 会用汇率、期货或上一交易日价格估算，所以它是参考值。本页选择 NAV，是因为历史曲线、分位和回测需要每天都用同一套规则比较。',
  'NAV 需要等基金公司披露后才能计算，因此可能和交易软件里的实时溢价率不同，最近一两天也可能暂时没有数据。它回答的是“今天收盘后确认，交易价格相对正式净值贵不贵”，不承担实时买卖提示的作用。',
]
const premiumLevelIntro = '本页用当前溢价率在所选区间内的历史分位判断高低：分位越高，代表当前价格相对 NAV 越贵。'
const explainLevelItems = [
  {
    label: '过高',
    detail: '历史分位 >= P90，处在自身历史高位。',
  },
  {
    label: '偏高',
    detail: 'P70 <= 历史分位 < P90，高于中游区间。',
  },
  {
    label: '中游',
    detail: 'P30 <= 历史分位 < P70，接近历史中枢。',
  },
  {
    label: '偏低',
    detail: 'P10 <= 历史分位 < P30，低于中游区间。',
  },
  {
    label: '过低',
    detail: '历史分位 < P10，处在自身历史低位。',
  },
]
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

const recentRows = computed(() => (
  filterByRange(history.value?.data || [], selectedRange.value)
    .slice(-5)
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
  grid-template-columns: repeat(2, 1fr);
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
  color: #0f172a;
  font-size: 25rpx;
  font-weight: 800;
  line-height: 36rpx;
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

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 1.05fr 1.25fr 1.45fr 1.05fr;
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
