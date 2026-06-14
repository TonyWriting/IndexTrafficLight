export interface PremiumRecord {
  date: string
  close: number
  nav: number
  premium_rate: number
}

export interface EtfInfo {
  code: string
  name: string
  short_name: string
  tracking_index: string
  tracking_index_name: string
  latest: PremiumRecord | null
}

export interface EtfPremiumHistory {
  code: string
  name: string
  short_name: string
  count: number
  data: PremiumRecord[]
}

export type PremiumRange = '1y' | '3y'

export interface RangeOption {
  value: PremiumRange
  label: string
}

export const RANGE_OPTIONS: RangeOption[] = [
  { value: '1y', label: '近1年' },
  { value: '3y', label: '近3年' },
]

export enum PremiumStatus {
  LOW = 1,
  BELOW_NORMAL = 2,
  NORMAL = 3,
  ABOVE_NORMAL = 4,
  EXTREME = 5,
}

export interface PremiumStatusConfig {
  label: string
  color: string
  bgColor: string
  borderColor: string
}

export const PREMIUM_STATUS_CONFIG: Record<PremiumStatus, PremiumStatusConfig> = {
  [PremiumStatus.LOW]: {
    label: '极低',
    color: '#047857',
    bgColor: '#ecfdf5',
    borderColor: '#10b981',
  },
  [PremiumStatus.BELOW_NORMAL]: {
    label: '偏低',
    color: '#15803d',
    bgColor: '#f0fdf4',
    borderColor: '#22c55e',
  },
  [PremiumStatus.NORMAL]: {
    label: '常态',
    color: '#92400e',
    bgColor: '#fffbeb',
    borderColor: '#f59e0b',
  },
  [PremiumStatus.ABOVE_NORMAL]: {
    label: '偏高',
    color: '#b45309',
    bgColor: '#fff7ed',
    borderColor: '#f97316',
  },
  [PremiumStatus.EXTREME]: {
    label: '极高',
    color: '#b91c1c',
    bgColor: '#fef2f2',
    borderColor: '#ef4444',
  },
}

export interface PremiumStats {
  latest: PremiumRecord | null
  count: number
  percentile: number
  status: PremiumStatus
  mean: number | null
  median: number | null
  p10: number | null
  p30: number | null
  p70: number | null
  p90: number | null
  min: number | null
  max: number | null
}

export const PREMIUM_LINE_COLOR = '#2563eb'
export const CLOSE_LINE_COLOR = '#64748b'

export const PERCENTILE_LINE_CONFIG = [
  { key: 'p90', label: 'P90', color: '#dc2626' },
  { key: 'p70', label: 'P70', color: '#ea580c' },
  { key: 'median', label: 'P50', color: '#ca8a04' },
  { key: 'p30', label: 'P30', color: '#16a34a' },
  { key: 'p10', label: 'P10', color: '#059669' },
] as const
