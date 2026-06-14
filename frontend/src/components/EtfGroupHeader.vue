<template>
  <view class="group-header">
    <view class="title-row">
      <text class="index-name" selectable>{{ trackingIndexName }}</text>
      <text class="member-count">{{ memberCount }} 只</text>
    </view>
    <view v-if="memberCount >= 2" class="range-row">
      <view class="range-item">
        <text class="range-label">最低溢价</text>
        <text class="range-value range-low" selectable>{{ formatPremiumRate(minPremium) }}</text>
      </view>
      <view class="range-divider" />
      <view class="range-item">
        <text class="range-label">最高溢价</text>
        <text class="range-value range-high" selectable>{{ formatPremiumRate(maxPremium) }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { formatPremiumRate } from '../utils/premium'

defineProps<{
  trackingIndexName: string
  memberCount: number
  minPremium: number | null
  maxPremium: number | null
}>()
</script>

<style scoped>
.group-header {
  padding: 22rpx 24rpx 18rpx;
  border-bottom: 1rpx solid #e2e8f0;
}

.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.index-name {
  min-width: 0;
  flex: 1;
  color: #0f172a;
  font-size: 30rpx;
  font-weight: 700;
  line-height: 40rpx;
}

.member-count {
  flex-shrink: 0;
  padding: 4rpx 14rpx;
  background: #f1f5f9;
  border: 1rpx solid #e2e8f0;
  border-radius: 999rpx;
  color: #475569;
  font-size: 22rpx;
  font-weight: 600;
  line-height: 30rpx;
}

.range-row {
  display: flex;
  align-items: center;
  margin-top: 14rpx;
}

.range-item {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.range-divider {
  width: 1rpx;
  height: 40rpx;
  margin: 0 18rpx;
  background: #e2e8f0;
}

.range-label {
  color: #94a3b8;
  font-size: 20rpx;
  line-height: 26rpx;
}

.range-value {
  font-size: 28rpx;
  font-weight: 700;
  line-height: 36rpx;
}

.range-low {
  color: #16a34a;
}

.range-high {
  color: #dc2626;
}
</style>
