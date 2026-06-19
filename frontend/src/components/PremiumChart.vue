<template>
  <view class="chart-panel">
    <view class="chart-head">
      <view class="chart-title-block">
        <text class="chart-title">溢价率走势</text>
      </view>
    </view>

    <view class="legend-row">
      <view class="legend-item">
        <view class="legend-gradient">
          <view
            v-for="zone in legendZones"
            :key="zone.key"
            class="legend-segment"
            :style="{ backgroundColor: zone.lineColor }"
          />
        </view>
        <text class="legend-text">溢价率</text>
      </view>
    </view>

    <view v-if="!hasChart" class="chart-empty">
      <text>暂无足够数据</text>
    </view>

    <cover-view v-if="tip.show" class="tooltip" :style="tipStyle">
      <cover-view class="tip-head">
        <cover-view class="tip-date">{{ tip.date }}</cover-view>
        <cover-view class="tip-close" @click="closeTip">x</cover-view>
      </cover-view>
      <cover-view class="tip-row">
        <cover-view class="tip-label">溢价率</cover-view>
        <cover-view class="tip-value">{{ tip.premium }}</cover-view>
      </cover-view>
      <cover-view class="tip-row">
        <cover-view class="tip-label">历史分位</cover-view>
        <cover-view class="tip-value">{{ tip.percentile }}</cover-view>
      </cover-view>
      <cover-view class="tip-row">
        <cover-view class="tip-label">场内收盘价</cover-view>
        <cover-view class="tip-value">{{ tip.close }}</cover-view>
      </cover-view>
      <cover-view class="tip-row">
        <cover-view class="tip-label">基金净值 NAV</cover-view>
        <cover-view class="tip-value">{{ tip.nav }}</cover-view>
      </cover-view>
    </cover-view>

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
import { PREMIUM_STATUS_CONFIG, PremiumStatus } from '../types'
import {
  filterByRange,
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

const BAND_DEFINITIONS = [
  {
    key: 'high',
    label: PREMIUM_STATUS_CONFIG[PremiumStatus.EXTREME].label,
    lowerKey: 'p90',
    upperKey: null,
    fillColor: '#fee2e2',
    lineColor: 'rgba(220, 38, 38, 0.82)',
    labelColor: 'rgba(185, 28, 28, 0.62)',
  },
  {
    key: 'above',
    label: PREMIUM_STATUS_CONFIG[PremiumStatus.ABOVE_NORMAL].label,
    lowerKey: 'p70',
    upperKey: 'p90',
    fillColor: '#ffedd5',
    lineColor: 'rgba(234, 88, 12, 0.78)',
    labelColor: 'rgba(194, 65, 12, 0.62)',
  },
  {
    key: 'normal',
    label: PREMIUM_STATUS_CONFIG[PremiumStatus.NORMAL].label,
    lowerKey: 'p30',
    upperKey: 'p70',
    fillColor: '#fff7ed',
    lineColor: 'rgba(217, 119, 6, 0.76)',
    labelColor: 'rgba(180, 83, 9, 0.58)',
  },
  {
    key: 'below',
    label: PREMIUM_STATUS_CONFIG[PremiumStatus.BELOW_NORMAL].label,
    lowerKey: 'p10',
    upperKey: 'p30',
    fillColor: '#ecfdf5',
    lineColor: 'rgba(34, 197, 94, 0.78)',
    labelColor: 'rgba(21, 128, 61, 0.62)',
  },
  {
    key: 'low',
    label: PREMIUM_STATUS_CONFIG[PremiumStatus.LOW].label,
    lowerKey: null,
    upperKey: 'p10',
    fillColor: '#dcfce7',
    lineColor: 'rgba(16, 185, 129, 0.82)',
    labelColor: 'rgba(4, 120, 87, 0.62)',
  },
] as const

const legendZones = BAND_DEFINITIONS.slice().reverse()

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
  bands: Array<{
    key: string
    label: string
    fillColor: string
    lineColor: string
    labelColor: string
    lower: number
    upper: number
  }>
  boundaries: number[]
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

function thresholdValue(key: string | null): number | null {
  if (!key) return null
  const value = statValue(key)
  return value == null ? null : value * 100
}

function createBands(yMin: number, yMax: number) {
  return BAND_DEFINITIONS
    .map((definition) => {
      const lower = thresholdValue(definition.lowerKey) ?? yMin
      const upper = thresholdValue(definition.upperKey) ?? yMax
      return {
        key: definition.key,
        label: definition.label,
        fillColor: definition.fillColor,
        lineColor: definition.lineColor,
        labelColor: definition.labelColor,
        lower: Math.max(yMin, Math.min(yMax, lower)),
        upper: Math.max(yMin, Math.min(yMax, upper)),
      }
    })
    .filter((band) => band.upper > band.lower)
}

function lineColorForValue(value: number): string {
  const p10 = thresholdValue('p10')
  const p30 = thresholdValue('p30')
  const p70 = thresholdValue('p70')
  const p90 = thresholdValue('p90')

  if (p90 != null && value >= p90) return BAND_DEFINITIONS[0].lineColor
  if (p70 != null && value >= p70) return BAND_DEFINITIONS[1].lineColor
  if (p30 != null && value >= p30) return BAND_DEFINITIONS[2].lineColor
  if (p10 != null && value >= p10) return BAND_DEFINITIONS[3].lineColor
  return BAND_DEFINITIONS[4].lineColor
}

function formatPercentileAsP(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'P--'
  return `P${Math.round(value * 100)}`
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
  const boundaries = ['p10', 'p30', 'p70', 'p90']
    .map(thresholdValue)
    .filter((value) => value != null)

  // Scale the Y axis to the data and percentile bands only. Forcing 0 into the
  // range would push the whole curve to one edge and inflate the outermost band
  // whenever the premium stays far from 0 (e.g. a persistently high premium).
  const allValues = values.concat(boundaries)
  const min = Math.min(...allValues)
  const max = Math.max(...allValues)
  const pad = Math.max((max - min) * 0.12, 0.8)
  const yMin = min - pad
  const yMax = max + pad

  cache = {
    records,
    rawValues,
    values,
    bands: createBands(yMin, yMax),
    boundaries,
    yMin,
    yMax,
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

function drawBandClippedLine(
  ctx: any,
  points: number[],
  toX: (index: number) => number,
  toY: (value: number) => number,
  band: { lineColor: string; lower: number; upper: number },
  padL: number,
  cw: number,
) {
  const yTop = toY(band.upper)
  const yBottom = toY(band.lower)

  ctx.save()
  ctx.beginPath()
  ctx.rect(padL, yTop, cw, yBottom - yTop)
  ctx.clip()
  drawLine(ctx, points, toX, toY, band.lineColor, 1.2)
  ctx.restore()
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
    const padR = 46
    const padT = 18
    const padB = 36
    const cw = W - padL - padR
    const ch = H - padT - padB
    meta = { padL, padR, padT, padB, cw, ch, W, H, left: rect.left || 0 }

    const { records, values, bands, boundaries, yMin, yMax, yRange } = cache
    const toX = (index: number) => padL + (index / (values.length - 1)) * cw
    const toY = (value: number) => padT + ch - ((value - yMin) / yRange) * ch

    ctx.clearRect(0, 0, W, H)
    ctx.setFillStyle('#ffffff')
    ctx.fillRect(0, 0, W, H)

    bands.forEach((band) => {
      const yTop = toY(band.upper)
      const yBottom = toY(band.lower)
      ctx.setFillStyle(band.fillColor)
      ctx.fillRect(padL, yTop - 1, cw, yBottom - yTop + 2)
    })

    ctx.setStrokeStyle('rgba(255, 255, 255, 0.42)')
    ctx.setLineWidth(1)
    boundaries.forEach((value) => {
      const y = toY(value)
      ctx.beginPath()
      ctx.moveTo(padL, y)
      ctx.lineTo(padL + cw, y)
      ctx.stroke()
    })

    ctx.setFillStyle('#64748b')
    ctx.setFontSize(11)
    ctx.setTextAlign('right')

    for (let i = 0; i <= 4; i++) {
      const y = padT + (i / 4) * ch
      const value = yMax - (yRange * i) / 4
      ctx.fillText(`${value.toFixed(1)}%`, padL - 6, y + 4)
    }

    ctx.setStrokeStyle('#e2e8f0')
    ctx.setLineWidth(1)
    ctx.beginPath()
    ctx.moveTo(padL, padT + ch)
    ctx.lineTo(padL + cw, padT + ch)
    ctx.moveTo(padL, padT + ch)
    ctx.lineTo(padL, padT)
    ctx.stroke()

    ctx.setFontSize(12)
    bands.forEach((band) => {
      const yTop = toY(band.upper)
      const yBottom = toY(band.lower)
      const y = yTop + (yBottom - yTop) / 2
      if (yBottom - yTop < 14) return
      ctx.setFillStyle(band.labelColor)
      ctx.setTextAlign('left')
      ctx.fillText(band.label, padL + cw + 7, y + 4)
    })

    ctx.setFillStyle('#64748b')
    ctx.setFontSize(11)
    ctx.setTextAlign('center')
    ctx.fillText(records[0].date, padL + 2, H - 10)
    ctx.fillText(records[records.length - 1].date, padL + cw - 2, H - 10)

    bands.slice().reverse().forEach((band) => {
      drawBandClippedLine(ctx, values, toX, toY, band, padL, cw)
    })

    if (crossIdx >= 0 && crossIdx < values.length) {
      const x = toX(crossIdx)
      const y = toY(values[crossIdx])
      ctx.setStrokeStyle('rgba(51, 65, 85, 0.55)')
      ctx.setLineWidth(1)
      ctx.setLineDash([4, 3])
      ctx.beginPath()
      ctx.moveTo(x, padT)
      ctx.lineTo(x, padT + ch)
      ctx.moveTo(padL, y)
      ctx.lineTo(padL + cw, y)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.setFillStyle(lineColorForValue(values[crossIdx]))
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
  tip.percentile = formatPercentileAsP(percentileRank(record.premium_rate, cache.rawValues))
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

.legend-gradient {
  width: 34rpx;
  height: 6rpx;
  display: flex;
  overflow: hidden;
  border-radius: 4rpx;
}

.legend-segment {
  flex: 1;
  height: 100%;
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
  padding: 18rpx 20rpx 20rpx;
  background: rgba(255, 255, 255, 0.92);
  border: 1rpx solid #e2e8f0;
  border-radius: 12rpx;
  box-shadow: 0 10rpx 24rpx rgba(15, 23, 42, 0.12);
}

.tip-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
  padding: 0 46rpx 8rpx 0;
  margin-bottom: 10rpx;
  border-bottom: 1rpx solid #e2e8f0;
}

.tip-date {
  color: #475569;
  font-size: 22rpx;
  line-height: 32rpx;
}

.tip-close {
  position: absolute;
  right: -4rpx;
  top: 4rpx;
  flex-shrink: 0;
  width: 50rpx;
  height: 50rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 26rpx;
  font-weight: 600;
  line-height: 50rpx;
  border-radius: 999rpx;
}

.tip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  min-height: 40rpx;
  line-height: 40rpx;
}

.tip-label {
  color: #64748b;
  font-size: 22rpx;
  line-height: 40rpx;
}

.tip-value {
  color: #0f172a;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 40rpx;
}
</style>
