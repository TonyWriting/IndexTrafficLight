<template>
  <view class="etf-mini-tile" @click="onClick">
    <view class="tile-head">
      <view class="tile-title-row">
        <text class="tile-name" selectable>{{ name }}</text>
        <view class="tile-badge" :style="{ backgroundColor: statusConfig.bgColor }">
          <text class="tile-badge-text" :style="{ color: statusConfig.color }" selectable>
            {{ statusConfig.label }}
          </text>
        </view>
      </view>
      <text class="tile-code" selectable>{{ codeLine }}</text>
    </view>
    <view class="tile-stats">
      <text class="tile-premium" :style="{ color: statusConfig.color }" selectable>
        {{ formatPremiumRate(latest?.premium_rate) }}
      </text>
      <text class="tile-percentile" selectable>P{{ percentileLabel }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DashboardLatestRecord, PremiumStatus } from '../types'
import { PREMIUM_STATUS_CONFIG } from '../types'
import { formatPremiumRate, formatShortDate } from '../utils/premium'

const props = defineProps<{
  code: string
  name: string
  latest: DashboardLatestRecord | null
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
.etf-mini-tile {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  padding: 18rpx 16rpx;
  background: #ffffff;
  border: 2rpx solid #e2e8f0;
  border-radius: 14rpx;
  box-shadow: 0 2rpx 8rpx rgba(15, 23, 42, 0.04);
}

.tile-head {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.tile-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10rpx;
}

.tile-name {
  flex: 1;
  min-width: 0;
  color: #0f172a;
  font-size: 24rpx;
  font-weight: 700;
  line-height: 32rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tile-badge {
  flex-shrink: 0;
  border-radius: 6rpx;
  padding: 2rpx 10rpx;
}

.tile-badge-text {
  font-size: 18rpx;
  font-weight: 700;
  line-height: 26rpx;
}

.tile-code {
  color: #64748b;
  font-size: 20rpx;
  line-height: 26rpx;
}

.tile-stats {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10rpx;
  margin-top: 6rpx;
}

.tile-premium {
  font-size: 34rpx;
  font-weight: 800;
  line-height: 42rpx;
}

.tile-percentile {
  flex-shrink: 0;
  color: #64748b;
  font-size: 22rpx;
  font-weight: 600;
  line-height: 28rpx;
}
</style>
