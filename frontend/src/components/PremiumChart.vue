<template>
  <view class="chart-panel">
    <view class="chart-head">
      <view class="chart-title-block">
        <text class="chart-title">溢价走势</text>
        <text class="chart-subtitle">{{ rangeLabel }} · {{ stats.count }} 个样本日</text>
      </view>
    </view>

    <view class="legend-row">
      <view class="legend-item">
        <view class="legend-solid" :style="{ backgroundColor: PREMIUM_LINE_COLOR }" />
        <text class="legend-text">溢价率</text>
      </view>
      <view
        v-for="line in percentileLines"
        :key="line.key"
        class="legend-item"
      >
        <view class="legend-dashed" :style="{ borderColor: line.color }" />
        <text class="legend-text">{{ line.label }}</text>
      </view>
    </view>

    <view v-if="!hasChart" class="chart-empty">
      <text>暂无足够数据</text>
    </view>

    <view v-if="tip.show" class="tooltip" :style="tipStyle">
      <view class="tip-head">
        <text class="tip-date">{{ tip.date }}</text>
        <text class="tip-close" @click="closeTip">x</text>
      </view>
      <view class="tip-row">
        <text class="tip-label">溢价率</text>
        <text class="tip-value">{{ tip.premium }}</text>
      </view>
      <view class="tip-row">
        <text class="tip-label">历史分位</text>
        <text class="tip-value">{{ tip.percentile }}</text>
      </view>
      <view class="tip-row">
        <text class="tip-label">收盘价</text>
        <text class="tip-value">{{ tip.close }}</text>
      </view>
      <view class="tip-row">
        <text class="tip-label">基金净值</text>
        <text class="tip-value">{{ tip.nav }}</text>
      </view>
    </view>

    <canvas
      :canvas-id="chartId"
      :id="chartId"
      class="chart-canvas"
      @touchstart="onDown"
      @touchmove="onMove"
      @touchend="onUp"
      @mousedown="onDown"
      @mousemove="onMove"
      @mouseup="onUp"
      @mouseleave="onUp"
    />
  </view>
</template>

<script setup lang="ts">
// @ts-nocheck
import { computed, getCurrentInstance, nextTick, onMounted, reactive, ref, watch } from 'vue'
import type { PremiumRange, PremiumRecord, PremiumStats } from '../types'
import { PERCENTILE_LINE_CONFIG, PREMIUM_LINE_COLOR, RANGE_OPTIONS } from '../types'
import {
  filterByRange,
  formatPercentile,
  formatPremiumRate,
  formatPrice,
  percentileRank,
} from '../utils/premium'

const props = withDefaults(defineProps<{
  records: PremiumRecord[]
  range: PremiumRange
  stats: PremiumStats
  canvasId?: string
}>(), {
  canvasId: 'premiumChart',
})

const instance = getCurrentInstance()
const chartId = computed(() => props.canvasId)
const hasChart = ref(false)
const isDragging = ref(false)
const percentileLines = PERCENTILE_LINE_CONFIG
const rangeLabel = computed(() => (
  RANGE_OPTIONS.find((option) => option.value === props.range)?.label || '全部'
))

const tip = reactive({
  show: false,
  date: '',
  premium: '',
  percentile: '',
  close: '',
  nav: '',
  x: 0,
  w: 0,
})

const tipStyle = computed(() => {
  const width = 178
  const gap = 14
  const panelWidth = tip.w || 320
  const left = panelWidth - tip.x < width + gap ? tip.x - width - gap : tip.x + gap
  return {
    left: `${Math.max(8, left)}px`,
    top: '28rpx',
  }
})

let cache: {
  records: PremiumRecord[]
  rawValues: number[]
  values: number[]
  refs: Array<{ key: string; label: string; color: string; value: number }>
  yMin: number
  yMax: number
  yRange: number
} | null = null

let meta = {
  padL: 42,
  padR: 24,
  padT: 16,
  padB: 34,
  cw: 0,
  ch: 0,
  W: 0,
  H: 0,
  left: 0,
}

let crossIdx = -1

function statValue(key: string): number | null {
  const value = props.stats[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function prepare() {
  const records = filterByRange(props.records, props.range)
  if (records.length < 2) {
    cache = null
    hasChart.value = false
    return
  }

  const rawValues = records.map((record) => record.premium_rate)
  const values = rawValues.map((value) => value * 100)
  const refs = PERCENTILE_LINE_CONFIG
    .map((line) => {
      const value = statValue(line.key)
      return value == null ? null : {
        key: line.key,
        label: line.label,
        color: line.color,
        value: value * 100,
      }
    })
    .filter(Boolean)

  const allValues = values.concat(refs.map((line) => line.value), [0])
  const min = Math.min(...allValues)
  const max = Math.max(...allValues)
  const pad = Math.max((max - min) * 0.12, 0.8)

  cache = {
    records,
    rawValues,
    values,
    refs,
    yMin: min - pad,
    yMax: max + pad,
    yRange: max - min + pad * 2,
  }
  hasChart.value = true
}

function drawLine(
  ctx: any,
  points: number[],
  toX: (index: number) => number,
  toY: (value: number) => number,
  color: string,
  width: number,
) {
  ctx.setStrokeStyle(color)
  ctx.setLineWidth(width)
  ctx.beginPath()
  points.forEach((value, index) => {
    const x = toX(index)
    const y = toY(value)
    index === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
  })
  ctx.stroke()
}

function draw() {
  if (!cache) return

  const ctx = uni.createCanvasContext(chartId.value, instance)
  const query = uni.createSelectorQuery().in(instance)

  query.select(`#${chartId.value}`).boundingClientRect((rect: any) => {
    if (!rect || !cache) return

    const W = rect.width
    const H = rect.height
    const padL = 46
    const padR = 34
    const padT = 18
    const padB = 36
    const cw = W - padL - padR
    const ch = H - padT - padB
    meta = { padL, padR, padT, padB, cw, ch, W, H, left: rect.left || 0 }

    const { records, values, refs, yMin, yMax, yRange } = cache
    const toX = (index: number) => padL + (index / (values.length - 1)) * cw
    const toY = (value: number) => padT + ch - ((value - yMin) / yRange) * ch

    ctx.clearRect(0, 0, W, H)
    ctx.setFillStyle('#ffffff')
    ctx.fillRect(0, 0, W, H)

    ctx.setFillStyle('#64748b')
    ctx.setFontSize(10)
    ctx.setTextAlign('right')

    for (let i = 0; i <= 4; i++) {
      const y = padT + (i / 4) * ch
      const value = yMax - (yRange * i) / 4
      ctx.fillText(`${value.toFixed(1)}%`, padL - 6, y + 4)
    }

    ctx.setStrokeStyle('#cbd5e1')
    ctx.setLineWidth(1)
    ctx.beginPath()
    ctx.moveTo(padL, padT + ch)
    ctx.lineTo(padL + cw + 10, padT + ch)
    ctx.moveTo(padL + cw + 10, padT + ch)
    ctx.lineTo(padL + cw + 4, padT + ch - 4)
    ctx.moveTo(padL + cw + 10, padT + ch)
    ctx.lineTo(padL + cw + 4, padT + ch + 4)
    ctx.moveTo(padL, padT + ch)
    ctx.lineTo(padL, padT - 10)
    ctx.moveTo(padL, padT - 10)
    ctx.lineTo(padL - 4, padT - 4)
    ctx.moveTo(padL, padT - 10)
    ctx.lineTo(padL + 4, padT - 4)
    ctx.stroke()

    refs.forEach((line) => {
      const y = toY(line.value)
      ctx.setStrokeStyle(line.color)
      ctx.setLineWidth(1)
      ctx.setLineDash([6, 4])
      ctx.beginPath()
      ctx.moveTo(padL, y)
      ctx.lineTo(padL + cw, y)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.setFillStyle(line.color)
      ctx.setTextAlign('left')
      ctx.fillText(line.label, padL + cw + 5, y + 4)
    })

    ctx.setFillStyle('#64748b')
    ctx.setTextAlign('center')
    const firstDate = records[0].date
    const firstYear = Number(firstDate.slice(0, 4))
    const lastYear = Number(records[records.length - 1].date.slice(0, 4))
    const yearTickIndexes: number[] = []

    for (let year = firstYear; year <= lastYear; year++) {
      const yearStart = `${year}-01-01`
      if (year === firstYear && firstDate !== yearStart) continue

      const index = records.findIndex((record) => record.date >= yearStart)
      if (index >= 0) yearTickIndexes.push(index)
    }

    yearTickIndexes.forEach((index) => {
      ctx.fillText(`${records[index].date.slice(0, 4)}年`, toX(index), H - 10)
    })

    drawLine(ctx, values, toX, toY, PREMIUM_LINE_COLOR, 2)

    if (crossIdx >= 0 && crossIdx < values.length) {
      const x = toX(crossIdx)
      const y = toY(values[crossIdx])
      ctx.setStrokeStyle('rgba(51, 65, 85, 0.55)')
      ctx.setLineWidth(1)
      ctx.setLineDash([4, 3])
      ctx.beginPath()
      ctx.moveTo(x, padT)
      ctx.lineTo(x, padT + ch)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.setFillStyle(PREMIUM_LINE_COLOR)
      ctx.beginPath()
      ctx.arc(x, y, 3, 0, 2 * Math.PI)
      ctx.fill()
    }

    ctx.draw()
  }).exec()
}

let lastInputAt = 0

function handleInput(event: any) {
  if (!cache || meta.cw <= 0) return

  const pointer = event.touches?.[0] || event.changedTouches?.[0] || event
  const x = pointer.x != null
    ? pointer.x
    : pointer.clientX != null
      ? pointer.clientX - meta.left
      : pointer.offsetX || 0

  const ratio = Math.max(0, Math.min(1, (x - meta.padL) / meta.cw))
  const index = Math.round(ratio * (cache.records.length - 1))
  const record = cache.records[index]

  tip.show = true
  tip.date = record.date
  tip.premium = formatPremiumRate(record.premium_rate)
  tip.percentile = formatPercentile(percentileRank(record.premium_rate, cache.rawValues))
  tip.close = formatPrice(record.close)
  tip.nav = formatPrice(record.nav)
  tip.x = x
  tip.w = meta.W
  crossIdx = index
  draw()
}

function throttledInput(event: any) {
  const now = Date.now()
  if (now - lastInputAt < 50) return
  lastInputAt = now
  handleInput(event)
}

function onDown(event: any) {
  isDragging.value = true
  handleInput(event)
}

function onMove(event: any) {
  if (isDragging.value || event.touches) throttledInput(event)
}

function onUp() {
  isDragging.value = false
}

function closeTip() {
  tip.show = false
  crossIdx = -1
  draw()
}

function redrawLater() {
  crossIdx = -1
  tip.show = false
  prepare()
  nextTick(() => setTimeout(draw, 80))
}

watch(() => [props.records, props.range, props.stats.count], redrawLater)

onMounted(redrawLater)
</script>

<style scoped>
.chart-panel {
  position: relative;
  background: #ffffff;
  border: 1rpx solid #e2e8f0;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-top: 20rpx;
}

.chart-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
}

.chart-title-block {
  min-width: 0;
}

.chart-title {
  display: block;
  color: #0f172a;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 38rpx;
}

.chart-subtitle {
  display: block;
  margin-top: 4rpx;
  color: #64748b;
  font-size: 22rpx;
  line-height: 30rpx;
}

.legend-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx 18rpx;
  margin-top: 18rpx;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.legend-solid {
  width: 28rpx;
  height: 5rpx;
  border-radius: 4rpx;
}

.legend-dashed {
  width: 28rpx;
  height: 0;
  border-top: 3rpx dashed;
}

.legend-text {
  color: #475569;
  font-size: 20rpx;
  line-height: 28rpx;
}

.chart-empty {
  position: absolute;
  left: 0;
  right: 0;
  top: 200rpx;
  z-index: 2;
  text-align: center;
  color: #94a3b8;
  font-size: 24rpx;
}

.chart-canvas {
  width: 100%;
  height: 500rpx;
  margin-top: 18rpx;
}

.tooltip {
  position: absolute;
  z-index: 5;
  min-width: 300rpx;
  padding: 16rpx 18rpx;
  background: rgba(255, 255, 255, 0.92);
  border: 1rpx solid #e2e8f0;
  border-radius: 12rpx;
  box-shadow: 0 10rpx 24rpx rgba(15, 23, 42, 0.12);
}

.tip-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding-bottom: 8rpx;
  margin-bottom: 8rpx;
  border-bottom: 1rpx solid #e2e8f0;
}

.tip-date,
.tip-close {
  color: #475569;
  font-size: 22rpx;
  line-height: 28rpx;
}

.tip-close {
  color: #94a3b8;
  padding: 0 6rpx;
}

.tip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  line-height: 34rpx;
}

.tip-label {
  color: #64748b;
  font-size: 22rpx;
}

.tip-value {
  color: #0f172a;
  font-size: 22rpx;
  font-weight: 700;
}
</style>
