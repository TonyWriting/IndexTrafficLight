<template>
  <view
    class="etf-card"
    @click="onClick"
  >
    <view class="card-top">
      <view class="title-block">
        <text class="fund-name" selectable>{{ name }}</text>
        <text class="fund-code" selectable>{{ codeLine }}</text>
      </view>
      <view class="status-badge" :style="{ backgroundColor: statusConfig.bgColor }">
        <text class="status-text" :style="{ color: statusConfig.color }" selectable>
          {{ statusConfig.label }}
        </text>
      </view>
    </view>

    <view class="primary-row">
      <view class="premium-block">
        <text class="metric-label">当前溢价</text>
        <text class="premium-value" :style="{ color: statusConfig.color }" selectable>
          {{ formatPremiumRate(latest?.premium_rate) }}
        </text>
      </view>
      <view class="rank-block">
        <text class="rank-value" selectable>P{{ percentileLabel }}</text>
        <text class="metric-label">历史分位</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PremiumRecord, PremiumStatus } from '../types'
import { PREMIUM_STATUS_CONFIG } from '../types'
import { formatPremiumRate, formatShortDate } from '../utils/premium'

const props = defineProps<{
  code: string
  name: string
  latest: PremiumRecord | null
  percentile: number
  status: PremiumStatus
}>()

const emit = defineEmits<{
  (e: 'click', code: string): void
}>()

const statusConfig = computed(() => PREMIUM_STATUS_CONFIG[props.status])

const codeLine = computed(() => {
  const date = props.latest?.date
  return date ? `${props.code} · ${formatShortDate(date)}` : props.code
})

const percentileLabel = computed(() => {
  if (!Number.isFinite(props.percentile)) return '--'
  return Math.round(props.percentile * 100).toString()
})

function onClick() {
  emit('click', props.code)
}
</script>

<style scoped>
.etf-card {
  background: #ffffff;
  border: 2rpx solid #e2e8f0;
  border-radius: 16rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 6rpx 20rpx rgba(15, 23, 42, 0.06);
}

.card-top {
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
  font-size: 32rpx;
  font-weight: 700;
  line-height: 42rpx;
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

.primary-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
  margin-top: 30rpx;
}

.premium-block,
.rank-block {
  min-width: 0;
}

.metric-label {
  display: block;
  color: #64748b;
  font-size: 22rpx;
  line-height: 30rpx;
}

.premium-value {
  display: block;
  margin-top: 4rpx;
  font-size: 48rpx;
  font-weight: 800;
  line-height: 58rpx;
}

.rank-block {
  text-align: right;
}

.rank-value {
  display: block;
  color: #0f172a;
  font-size: 34rpx;
  font-weight: 700;
  line-height: 44rpx;
}
</style>
