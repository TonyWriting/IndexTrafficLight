<template>
  <view class="etf-mini-tile" @click="onClick">
    <view class="tile-head">
      <view class="tile-title-row">
        <view class="tile-title">
          <text class="tile-name" selectable>{{ name }}</text>
          <text v-if="rating" class="tile-rating" selectable><text class="rating-separator">· </text>{{ rating }}</text>
        </view>
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
import type { FundRating } from '../config/etfDisplay'
import { PREMIUM_STATUS_CONFIG } from '../types'
import { formatPremiumRate, formatShortDate } from '../utils/premium'

const props = defineProps<{
  code: string
  name: string
  rating?: FundRating | null
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
  flex: 0 1 auto;
  min-width: 0;
  color: #0f172a;
  font-size: 24rpx;
  font-weight: 700;
  line-height: 32rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tile-title {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  min-width: 0;
  flex: 1;
}

.tile-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-sizing: border-box;
  height: 32rpx;
  padding: 0 8rpx;
  border: 1rpx solid transparent;
  border-radius: 6rpx;
  white-space: nowrap;
}

.tile-badge-text {
  font-size: 18rpx;
  font-weight: 700;
  line-height: 26rpx;
}

.tile-code,
.tile-rating {
  color: #64748b;
  font-size: 20rpx;
  line-height: 26rpx;
}

.tile-rating {
  flex-shrink: 0;
  white-space: nowrap;
  color: rgba(91, 33, 182, 0.75);
  font-weight: 600;
}

.rating-separator {
  color: #64748b;
  font-weight: 400;
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
