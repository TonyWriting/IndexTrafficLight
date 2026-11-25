export interface PremiumRecord {
  date: string
  close: number
  nav: number | null
  nav_date: string | null
  iopv: number | null
  premium_basis: 'iopv' | 'nav_proxy_iopv'
  premium_rate: number
}

export type FundType = 'etf' | 'lof'

export interface EtfInfo {
  code: string
  name: string
  short_name: string
  fund_type: FundType
  tracking_index: string
  tracking_index_name: string
  latest: PremiumRecord | null
}

export interface EtfPremiumHistory {
  code: string
  name: string
  short_name: string
  fund_type: FundType
  count: number
  data: PremiumRecord[]
}

export type PremiumRange = '3m' | '6m' | '1y'

export interface RangeOption {
  value: PremiumRange
  label: string
}

export const RANGE_OPTIONS: RangeOption[] = [
  { value: '3m', label: '近3月' },
  { value: '6m', label: '近半年' },
  { value: '1y', label: '近1年' },
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
    label: '过低',
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
    label: '中游',
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
    label: '过高',
    color: '#b91c1c',
    bgColor: '#fef2f2',
    borderColor: '#ef4444',
  },
}

export const PREMIUM_LEVEL_LINE_COLORS: Record<PremiumStatus, string> = {
  [PremiumStatus.LOW]: 'rgba(16, 185, 129, 0.82)',
  [PremiumStatus.BELOW_NORMAL]: 'rgba(34, 197, 94, 0.78)',
  [PremiumStatus.NORMAL]: 'rgba(217, 119, 6, 0.76)',
  [PremiumStatus.ABOVE_NORMAL]: 'rgba(234, 88, 12, 0.78)',
  [PremiumStatus.EXTREME]: 'rgba(220, 38, 38, 0.82)',
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
}

export interface DashboardRangeSummary {
  min_premium: number | null
  max_premium: number | null
}

export interface DashboardLatestRecord {
  date: string
  premium_rate: number
}

export interface DashboardStats {
  latest: DashboardLatestRecord | null
  percentile: number
  status: PremiumStatus
}

export interface DashboardItem {
  code: string
  name: string
  short_name: string
  fund_type: FundType
  stats: Record<PremiumRange, DashboardStats>
}

export interface DashboardGroup {
  tracking_index: string
  tracking_index_name: string
  members: string[]
  ranges: Record<PremiumRange, DashboardRangeSummary>
}

export interface DashboardSnapshot {
  items: DashboardItem[]
  groups: DashboardGroup[]
}

export const CLOSE_LINE_COLOR = '#64748b'
