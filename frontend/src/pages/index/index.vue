<template>
  <view v-if="viewMode === 'calculator'" class="page">
    <view class="hero">
      <text class="title">偏离率计算器</text>
      <text class="subtitle">计算当前值相对基准值偏高或偏低多少</text>
    </view>

    <view class="calculator">
      <view class="input-row">
        <text class="input-label">当前值</text>
        <input
          class="number-input"
          type="digit"
          :value="currentValue"
          placeholder="请输入当前值"
          @input="onCurrentInput"
        />
      </view>

      <view class="input-row">
        <text class="input-label">基准值</text>
        <input
          class="number-input"
          type="digit"
          :value="baseValue"
          placeholder="请输入基准值"
          @input="onBaseInput"
        />
      </view>

      <view class="result-panel" :class="resultTone">
        <view>
          <text class="result-label">偏离率</text>
          <text class="result-value">{{ deviationLabel }}</text>
        </view>
        <view class="status-pill">
          <text>{{ statusLabel }}</text>
        </view>
      </view>

      <text class="formula">计算公式：当前值 / 基准值 - 1</text>
    </view>

    <view class="examples">
      <view class="section-head">
        <text class="section-title">示例场景</text>
        <text class="section-subtitle">点击示例可快速填入</text>
      </view>

      <view class="example-grid">
        <view
          v-for="item in examples"
          :key="item.name"
          class="example-card"
          @click="applyExample(item)"
        >
          <view class="example-top">
            <text class="example-name">{{ item.name }}</text>
            <text class="example-badge" :class="exampleTone(item)">{{ exampleStatus(item) }}</text>
          </view>
          <view class="example-values">
            <text>当前 {{ formatNumber(item.current) }}</text>
            <text>基准 {{ formatNumber(item.base) }}</text>
          </view>
          <text class="example-rate" :class="exampleTone(item)">
            {{ formatDeviation(calculateDeviation(item.current, item.base)) }}
          </text>
        </view>
      </view>
    </view>

    <view class="tips">
      <text class="tips-title">适用场景</text>
      <text class="tips-text">可用于学习记录、项目进度、习惯打卡、工作统计、公开数据统计等自定义指标。</text>
    </view>
  </view>

  <view v-else class="dashboard">
    <view
      v-if="!loading && !error && dashboardGroups.length > 0"
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
          :collapsible="group.members.length > 2"
          :expanded="group.expanded"
          @toggle="toggleGroup(group.tracking_index)"
        />
        <view v-if="group.expanded" class="group-body">
          <view v-if="group.members.length >= 2" class="tile-grid">
            <EtfMiniTile
              v-for="item in group.members"
              :key="item.code"
              :code="item.code"
              :name="item.displayName"
              :rating="item.rating"
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
            :rating="item.rating"
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
import { onHide, onPullDownRefresh, onShareAppMessage, onShareTimeline, onShow, onUnload } from '@dcloudio/uni-app'
import EtfCard from '../../components/EtfCard.vue'
import EtfGroupHeader from '../../components/EtfGroupHeader.vue'
import EtfMiniTile from '../../components/EtfMiniTile.vue'
import {
  fetchDashboard,
  fetchReviewMode,
  PREMIUM_CACHE_UPDATED_EVENT,
  startPremiumAutoRefresh,
  stopPremiumAutoRefresh,
} from '../../api'
import type { DashboardSnapshot, DashboardStats, PremiumRange, PremiumStatus } from '../../types'
import { RANGE_OPTIONS } from '../../types'
import { ETF_DISPLAY } from '../../config/etfDisplay'
import type { FundRating } from '../../config/etfDisplay'

interface DashboardItem {
  code: string
  displayName: string
  rating: FundRating | null
  order: number
  stats: DashboardStats
}

interface DashboardGroup {
  tracking_index: string
  tracking_index_name: string
  members: DashboardItem[]
  expanded: boolean
  min_premium: number | null
  max_premium: number | null
  min_status: PremiumStatus | null
  max_status: PremiumStatus | null
}

interface ExampleItem {
  name: string
  current: number
  base: number
}

const viewMode = ref<'dashboard' | 'calculator'>('dashboard')
const loading = ref(true)
const error = ref('')
const dashboard = ref<DashboardSnapshot | null>(null)
const selectedRange = ref<PremiumRange>('3m')
const expandedGroups = ref<Record<string, boolean>>({})
let pageVisible = false

function toggleGroup(trackingIndex: string) {
  expandedGroups.value[trackingIndex] = !expandedGroups.value[trackingIndex]
}

const currentValue = ref('82')
const baseValue = ref('75')
const examples: ExampleItem[] = [
  { name: '任务完成率', current: 82, base: 75 },
  { name: '阅读时长', current: 45, base: 30 },
  { name: '响应时长', current: 42, base: 50 },
  { name: '练习次数', current: 18, base: 20 },
]

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
          displayName: ETF_DISPLAY[item.code]?.companyName || item.short_name || item.name || item.code,
          rating: ETF_DISPLAY[item.code]?.rating ?? null,
          order: ETF_DISPLAY[item.code]?.order ?? Number.POSITIVE_INFINITY,
          stats: item.stats[selectedRange.value],
        }))
        .filter((item) => item.stats.latest)

      members.sort((a, b) => a.order - b.order || a.code.localeCompare(b.code))

      const range = group.ranges[selectedRange.value]
      const minMember = members.find((item) => item.stats.latest?.premium_rate === range.min_premium)
      const maxMember = members.find((item) => item.stats.latest?.premium_rate === range.max_premium)

      return {
        tracking_index: group.tracking_index,
        tracking_index_name: group.tracking_index_name,
        members,
        expanded: members.length <= 2 || expandedGroups.value[group.tracking_index] === true,
        min_premium: range.min_premium,
        max_premium: range.max_premium,
        min_status: minMember?.stats.status ?? null,
        max_status: maxMember?.stats.status ?? null,
      }
    })
    .filter((group) => group.members.length > 0)
})

const currentNumber = computed(() => parseInput(currentValue.value))
const baseNumber = computed(() => parseInput(baseValue.value))
const deviation = computed(() => calculateDeviation(currentNumber.value, baseNumber.value))
const deviationLabel = computed(() => formatDeviation(deviation.value))
const resultTone = computed(() => toneForDeviation(deviation.value))
const statusLabel = computed(() => statusForDeviation(deviation.value))

async function initializePage(): Promise<void> {
  const reviewMode = await fetchReviewMode()
  if (reviewMode) {
    showCalculator()
    return
  }

  await loadData(false, dashboard.value !== null)
}

function showDashboard(snapshot: DashboardSnapshot): void {
  viewMode.value = 'dashboard'
  dashboard.value = snapshot
  loading.value = false
  error.value = ''
  if (pageVisible) {
    uni.setNavigationBarTitle({ title: 'QDII 场内基金溢价灯' })
    startPremiumAutoRefresh()
  }
}

function showCalculator(): void {
  viewMode.value = 'calculator'
  loading.value = false
  error.value = ''
  if (pageVisible) {
    stopPremiumAutoRefresh()
    uni.setNavigationBarTitle({ title: '偏离率计算器' })
  }
}

async function loadData(forceRefresh = false, silent = false): Promise<boolean> {
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    const data = await fetchDashboard(forceRefresh)
    showDashboard(data)
    return true
  } catch (err: any) {
    if (!silent) {
      error.value = err?.message || '数据加载失败'
    }
    return false
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

function openDetail(code: string) {
  uni.navigateTo({ url: `/pages/detail/detail?code=${encodeURIComponent(code)}` })
}

function handlePremiumCacheUpdated(snapshot: DashboardSnapshot) {
  if (viewMode.value === 'dashboard') {
    dashboard.value = snapshot
    error.value = ''
  }
}

function parseInput(value: string): number | null {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function calculateDeviation(current: number | null, base: number | null): number | null {
  if (current === null || base === null || base === 0) return null
  return current / base - 1
}

function formatDeviation(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '--'
  const sign = value > 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(1)}%`
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? value.toString() : value.toFixed(2)
}

function toneForDeviation(value: number | null): string {
  if (value === null || Math.abs(value) < 0.0001) return 'neutral'
  return value > 0 ? 'positive' : 'negative'
}

function statusForDeviation(value: number | null): string {
  if (value === null) return '待计算'
  if (Math.abs(value) < 0.0001) return '持平'
  return value > 0 ? '偏高' : '偏低'
}

function exampleTone(item: ExampleItem): string {
  return toneForDeviation(calculateDeviation(item.current, item.base))
}

function exampleStatus(item: ExampleItem): string {
  return statusForDeviation(calculateDeviation(item.current, item.base))
}

function applyExample(item: ExampleItem): void {
  currentValue.value = item.current.toString()
  baseValue.value = item.base.toString()
}

function onCurrentInput(event: any): void {
  currentValue.value = event.detail.value
}

function onBaseInput(event: any): void {
  baseValue.value = event.detail.value
}

onMounted(() => {
  uni.$on(PREMIUM_CACHE_UPDATED_EVENT, handlePremiumCacheUpdated)
})

onUnmounted(() => {
  uni.$off(PREMIUM_CACHE_UPDATED_EVENT, handlePremiumCacheUpdated)
})

onShow(() => {
  pageVisible = true
  void initializePage()
})

function stopPageRefresh(): void {
  if (!pageVisible) return
  pageVisible = false
  stopPremiumAutoRefresh()
}

onHide(stopPageRefresh)
onUnload(stopPageRefresh)

onPullDownRefresh(async () => {
  if (viewMode.value === 'dashboard') {
    await loadData(true)
  }
  uni.stopPullDownRefresh()
})

onShareAppMessage(() => ({
  title: viewMode.value === 'calculator'
    ? '偏离率计算器'
    : 'QDII 场内基金溢价灯 · 盘后看场内价格贵不贵',
  path: '/pages/index/index',
}))

onShareTimeline(() => ({
  title: viewMode.value === 'calculator'
    ? '偏离率计算器'
    : 'QDII 场内基金溢价灯 · 盘后看场内价格贵不贵',
}))
</script>

<style scoped>
.dashboard,
.page {
  min-height: 100vh;
  padding: 28rpx 24rpx 40rpx;
  background: #f1f5f9;
  box-sizing: border-box;
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

.hero {
  margin-bottom: 24rpx;
}

.title {
  display: block;
  color: #111827;
  font-size: 42rpx;
  font-weight: 800;
  line-height: 54rpx;
}

.subtitle {
  display: block;
  margin-top: 8rpx;
  color: #6b7280;
  font-size: 25rpx;
  line-height: 36rpx;
}

.calculator,
.examples,
.tips {
  background: #ffffff;
  border: 1rpx solid #e5e7eb;
  border-radius: 16rpx;
  padding: 24rpx;
  box-shadow: 0 4rpx 14rpx rgba(17, 24, 39, 0.05);
}

.input-row {
  margin-bottom: 18rpx;
}

.input-label {
  display: block;
  margin-bottom: 8rpx;
  color: #374151;
  font-size: 24rpx;
  font-weight: 700;
  line-height: 34rpx;
}

.number-input {
  height: 76rpx;
  padding: 0 20rpx;
  color: #111827;
  font-size: 30rpx;
  background: #f9fafb;
  border: 1rpx solid #d1d5db;
  border-radius: 12rpx;
  box-sizing: border-box;
}

.result-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  margin-top: 26rpx;
  padding: 24rpx;
  border-radius: 14rpx;
  border: 2rpx solid #d1d5db;
  background: #f9fafb;
}

.result-panel.positive {
  border-color: #f59e0b;
  background: #fffbeb;
}

.result-panel.negative {
  border-color: #10b981;
  background: #ecfdf5;
}

.result-label {
  display: block;
  color: #6b7280;
  font-size: 23rpx;
  line-height: 32rpx;
}

.result-value {
  display: block;
  margin-top: 2rpx;
  color: #111827;
  font-size: 48rpx;
  font-weight: 800;
  line-height: 58rpx;
}

.status-pill {
  flex-shrink: 0;
  min-width: 96rpx;
  padding: 10rpx 16rpx;
  background: #ffffff;
  border-radius: 999rpx;
  text-align: center;
}

.status-pill text {
  color: #374151;
  font-size: 24rpx;
  font-weight: 700;
}

.formula {
  display: block;
  margin-top: 16rpx;
  color: #6b7280;
  font-size: 22rpx;
  line-height: 32rpx;
}

.examples {
  margin-top: 22rpx;
}

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.section-title {
  color: #111827;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 40rpx;
}

.section-subtitle {
  color: #9ca3af;
  font-size: 22rpx;
  line-height: 32rpx;
}

.example-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14rpx;
}

.example-card {
  min-width: 0;
  padding: 18rpx;
  background: #f9fafb;
  border: 1rpx solid #e5e7eb;
  border-radius: 12rpx;
}

.example-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8rpx;
}

.example-name {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #111827;
  font-size: 24rpx;
  font-weight: 800;
  line-height: 32rpx;
}

.example-badge {
  flex-shrink: 0;
  font-size: 20rpx;
  font-weight: 700;
  line-height: 28rpx;
}

.example-values {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
  margin-top: 10rpx;
}

.example-values text {
  color: #6b7280;
  font-size: 21rpx;
  line-height: 30rpx;
}

.example-rate {
  display: block;
  margin-top: 8rpx;
  font-size: 32rpx;
  font-weight: 800;
  line-height: 40rpx;
}

.positive {
  color: #b45309;
}

.negative {
  color: #047857;
}

.neutral {
  color: #4b5563;
}

.tips {
  margin-top: 22rpx;
}

.tips-title {
  display: block;
  color: #111827;
  font-size: 28rpx;
  font-weight: 800;
  line-height: 38rpx;
}

.tips-text {
  display: block;
  margin-top: 8rpx;
  color: #6b7280;
  font-size: 24rpx;
  line-height: 38rpx;
}
</style>
