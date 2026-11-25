import type { PremiumRange, PremiumRecord, PremiumStats } from '../types'
import { PremiumStatus } from '../types'

const RANGE_MONTHS: Record<PremiumRange, number> = {
  '3m': 3,
  '6m': 6,
  '1y': 12,
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate()
}

function shiftMonth(dateStr: string, months: number): string {
  const [year, month, day] = dateStr.split('-').map(Number)
  const monthIndex = year * 12 + month - 1 + months
  const targetYear = Math.floor(monthIndex / 12)
  const targetMonth = (monthIndex % 12) + 1
  const targetDay = Math.min(day, daysInMonth(targetYear, targetMonth))
  return [
    String(targetYear).padStart(4, '0'),
    String(targetMonth).padStart(2, '0'),
    String(targetDay).padStart(2, '0'),
  ].join('-')
}

function normalizeRecords(records: PremiumRecord[]): PremiumRecord[] {
  return records
    .filter((record) => (
      !!record.date
      && isFiniteNumber(record.close)
      && isFiniteNumber(record.iopv ?? record.nav)
      && isFiniteNumber(record.premium_rate)
    ))
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))
}

export function filterByRange(
  records: PremiumRecord[],
  range: PremiumRange,
): PremiumRecord[] {
  const sorted = normalizeRecords(records)
  if (sorted.length === 0) return sorted

  const latestDate = sorted[sorted.length - 1].date
  const cutoff = shiftMonth(latestDate, -RANGE_MONTHS[range])
  return sorted.filter((record) => record.date >= cutoff)
}

function quantile(values: number[], q: number): number | null {
  const sorted = values
    .filter(isFiniteNumber)
    .slice()
    .sort((a, b) => a - b)

  if (sorted.length === 0) return null
  if (sorted.length === 1) return sorted[0]

  const pos = (sorted.length - 1) * q
  const base = Math.floor(pos)
  const rest = pos - base
  const next = sorted[base + 1]

  if (next == null) return sorted[base]
  return sorted[base] + rest * (next - sorted[base])
}

export function percentileRank(current: number, values: number[]): number {
  const clean = values.filter(isFiniteNumber)
  if (clean.length === 0) return 0.5

  const countBelowOrEqual = clean.filter((value) => value <= current).length
  return Math.max(0, Math.min(1, countBelowOrEqual / clean.length))
}

function determinePremiumStatus(percentile: number): PremiumStatus {
  if (percentile >= 0.9) return PremiumStatus.EXTREME
  if (percentile >= 0.7) return PremiumStatus.ABOVE_NORMAL
  if (percentile >= 0.3) return PremiumStatus.NORMAL
  if (percentile >= 0.1) return PremiumStatus.BELOW_NORMAL
  return PremiumStatus.LOW
}

export function summarizePremium(
  records: PremiumRecord[],
  range: PremiumRange,
): PremiumStats {
  const filtered = filterByRange(records, range)
  const values = filtered.map((record) => record.premium_rate)
  const latest = filtered[filtered.length - 1] ?? null

  if (!latest || values.length === 0) {
    return {
      latest: null,
      count: 0,
      percentile: 0.5,
      status: PremiumStatus.NORMAL,
      mean: null,
      median: null,
      p10: null,
      p30: null,
      p70: null,
      p90: null,
    }
  }

  const percentile = percentileRank(latest.premium_rate, values)
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length

  return {
    latest,
    count: values.length,
    percentile,
    status: determinePremiumStatus(percentile),
    mean,
    median: quantile(values, 0.5),
    p10: quantile(values, 0.1),
    p30: quantile(values, 0.3),
    p70: quantile(values, 0.7),
    p90: quantile(values, 0.9),
  }
}

export function formatPremiumRate(value: number | null | undefined, digits = 2): string {
  if (!isFiniteNumber(value)) return '--'
  const pct = value * 100
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(digits)}%`
}

export function formatPrice(value: number | null | undefined, digits = 3): string {
  if (!isFiniteNumber(value)) return '--'
  return value.toFixed(digits)
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) return '--'
  const match = /^\d{4}-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return value
  return `${parseInt(match[1], 10)}月${parseInt(match[2], 10)}日`
}
