<template>
  <view class="group-header" :class="{ collapsed: collapsible && !expanded }">
    <view class="title-row" :class="{ collapsible }" @click="toggle">
      <text class="index-name">{{ trackingIndexName }}</text>
      <text class="member-count">{{ memberCount }} 只</text>
      <view
        v-if="collapsible"
        class="collapse-toggle"
        role="button"
        tabindex="0"
        :aria-label="expanded ? '收起' : '展开'"
        :aria-expanded="expanded"
        @keydown.enter.stop.prevent="toggle"
        @keydown.space.stop.prevent="toggle"
      >
        <view class="collapse-triangle" :class="{ expanded }" />
      </view>
    </view>
    <view v-if="memberCount >= 2 && (!collapsible || expanded)" class="range-row">
      <view class="range-item">
        <text class="range-label">最低溢价率</text>
        <text class="range-value" :style="{ color: minColor }" selectable>
          {{ formatPremiumRate(minPremium) }}
        </text>
      </view>
      <view class="range-divider" />
      <view class="range-item">
        <text class="range-label">最高溢价率</text>
        <text class="range-value" :style="{ color: maxColor }" selectable>
          {{ formatPremiumRate(maxPremium) }}
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PremiumStatus } from '../types'
import { PREMIUM_STATUS_CONFIG } from '../types'
import { formatPremiumRate } from '../utils/premium'

const props = defineProps<{
  trackingIndexName: string
  memberCount: number
  minPremium: number | null
  maxPremium: number | null
  minStatus: PremiumStatus | null
  maxStatus: PremiumStatus | null
  collapsible?: boolean
  expanded?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle'): void
}>()

function toggle() {
  if (props.collapsible) emit('toggle')
}

const fallbackColor = '#475569'
const minColor = computed(() => (
  props.minStatus ? PREMIUM_STATUS_CONFIG[props.minStatus].color : fallbackColor
))
const maxColor = computed(() => (
  props.maxStatus ? PREMIUM_STATUS_CONFIG[props.maxStatus].color : fallbackColor
))
</script>

<style scoped>
.group-header {
  padding: 22rpx 24rpx 18rpx;
  border-bottom: 1rpx solid #e2e8f0;
}

.group-header.collapsed {
  border-bottom: 0;
}

.title-row.collapsible {
  cursor: pointer;
}

.collapse-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44rpx;
  min-height: 44rpx;
  flex-shrink: 0;
}

.collapse-triangle {
  width: 0;
  height: 0;
  border-top: 8rpx solid transparent;
  border-bottom: 8rpx solid transparent;
  border-left: 11rpx solid #64748b;
  transition: transform 0.15s ease;
}

.collapse-triangle.expanded {
  transform: rotate(90deg);
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
</style>
