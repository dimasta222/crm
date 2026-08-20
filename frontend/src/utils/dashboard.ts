import { dayjs } from 'frappe-ui'
import { getCurrentLocale } from '@/translation'

export const PRINT_STUDIO_NUMBER_CHARTS = [
  { label: 'Total order amount', value: 'total_order_amount' },
  { label: 'Paid for period orders', value: 'paid_for_period_orders' },
  { label: 'Awaiting Payment', value: 'awaiting_payment' },
  { label: 'Current orders (now)', value: 'current_orders' },
  { label: 'Completed orders', value: 'completed_orders' },
  { label: 'Average order value', value: 'average_order_value' },
  { label: 'Orders in production (now)', value: 'orders_in_production' },
  {
    label: 'Ready for pickup (now)',
    value: 'orders_ready_for_pickup',
  },
  { label: 'Overdue orders (now)', value: 'overdue_orders' },
  { label: 'Unpaid orders (now)', value: 'unpaid_orders' },
] as const

export const PRINT_STUDIO_AXIS_CHARTS = [
  {
    label: 'Completed order amount by day',
    value: 'completed_order_amount_by_day',
  },
  {
    label: 'Orders by production type',
    value: 'orders_by_production_type',
  },
  {
    label: 'Orders by acquisition manager',
    value: 'orders_by_acquisition_manager',
  },
  {
    label: 'Outstanding balance by payment status (now)',
    value: 'outstanding_balance_by_payment_status',
  },
] as const

export const PRINT_STUDIO_DONUT_CHARTS = [
  { label: 'Current statuses of period orders', value: 'orders_by_status' },
  { label: 'Orders by source', value: 'orders_by_source' },
] as const

export type DashboardPeriod =
  | 'Today'
  | 'Yesterday'
  | 'Last 7 Days'
  | 'Last 30 Days'
  | 'Last 60 Days'
  | 'Last 90 Days'
  | 'Custom Range'

export const PRINT_STUDIO_MONETARY_METRICS = new Set([
  'total_order_amount',
  'paid_for_period_orders',
  'awaiting_payment',
  'average_order_value',
])

export const PRINT_STUDIO_MONETARY_AXIS_CHARTS = new Set([
  'completed_order_amount_by_day',
  'outstanding_balance_by_payment_status',
])

type ChartValue = number | string | null | undefined
type EChartOptions = Record<string, unknown>
type DashboardSeries = Record<string, unknown> & {
  echartOptions?: EChartOptions & { label?: EChartOptions }
}
type DashboardAxisConfig = Record<string, unknown> & {
  swapXY?: boolean
  xAxis?: Record<string, unknown> & {
    type?: string
    timeGrain?: string
  }
  yAxis?: Record<string, unknown> & {
    echartOptions?: EChartOptions & { axisLabel?: EChartOptions }
  }
  series?: DashboardSeries[]
  echartOptions?: EChartOptions & { tooltip?: EChartOptions }
}
type EChartFormatterParams = {
  value?: unknown[]
  marker?: string
  seriesName?: string
}

export function isDashboardCurrencyCard(metricType: string | undefined) {
  return Boolean(metricType && PRINT_STUDIO_MONETARY_METRICS.has(metricType))
}

export function formatDashboardCurrency(
  value: number | string | null | undefined,
  symbol = '',
) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string' && !value.trim()) return '—'

  const formatted =
    typeof value === 'string'
      ? formatDecimalString(value)
      : formatFiniteNumber(value)
  if (!formatted) return '—'

  return `${formatted}${symbol ? ` ${symbol}` : ''}`
}

export function getDashboardCurrencyValueClass(formatted: string) {
  if (formatted.length >= 26) return 'text-sm'
  if (formatted.length > 18) return 'text-lg'
  return 'text-2xl'
}

function formatFiniteNumber(value: number) {
  if (!Number.isFinite(value)) return null
  const fractionDigits = Number.isInteger(value) ? 0 : 2
  return normalizeSpaces(
    new Intl.NumberFormat(getCurrentLocale(), {
      notation: 'standard',
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
      useGrouping: false,
    }).format(value),
  )
}

function formatDecimalString(value: string) {
  const match = value.trim().match(/^([+-]?)(\d+)(?:\.(\d+))?$/)
  if (!match) return null

  const [, sign, integer, fraction = ''] = match
  const precision = 2
  const scale = 10n ** BigInt(precision)
  let scaled = BigInt(integer) * scale
  if (precision) {
    scaled += BigInt(fraction.slice(0, precision).padEnd(precision, '0'))
  }
  if (fraction.length > precision && fraction[precision] >= '5') scaled += 1n

  const scaledText = scaled.toString().padStart(precision + 1, '0')
  const integerText = precision ? scaledText.slice(0, -precision) : scaledText
  const fractionText = precision ? scaledText.slice(-precision) : ''
  const locale = getCurrentLocale()
  const isZero = scaled === 0n
  const minus =
    sign === '-' && !isZero ? getNumberPart(locale, -1, 'minusSign') : ''
  const decimal = getNumberPart(locale, 1.1, 'decimal') || '.'
  const visibleFraction = fractionText && BigInt(fractionText) !== 0n
  return `${minus}${integerText}${visibleFraction ? decimal + fractionText : ''}`
}

export function getDashboardChartConfig(item: {
  name?: string
  type?: string
  data?: DashboardAxisConfig
}) {
  const config = item.data
  if (
    item.type !== 'axis_chart' ||
    !item.name ||
    !PRINT_STUDIO_MONETARY_AXIS_CHARTS.has(item.name) ||
    !config
  ) {
    return config
  }

  const formatAmount = (value: unknown) =>
    formatDashboardCurrency(asChartValue(value))
  const formatSeriesValue = (params: EChartFormatterParams) => {
    const value = config.swapXY ? params?.value?.[0] : params?.value?.[1]
    return formatAmount(value)
  }

  return {
    ...config,
    yAxis: {
      ...config.yAxis,
      echartOptions: {
        ...config.yAxis?.echartOptions,
        axisLabel: {
          ...config.yAxis?.echartOptions?.axisLabel,
          formatter: formatAmount,
        },
      },
    },
    series: (config.series || []).map((series) => ({
      ...series,
      echartOptions: {
        ...series.echartOptions,
        label: {
          ...series.echartOptions?.label,
          formatter: formatSeriesValue,
        },
      },
    })),
    echartOptions: {
      ...config.echartOptions,
      tooltip: {
        ...config.echartOptions?.tooltip,
        formatter: (params: EChartFormatterParams | EChartFormatterParams[]) =>
          formatMonetaryAxisTooltip(params, config, formatAmount),
      },
    },
  }
}

function formatMonetaryAxisTooltip(
  params: EChartFormatterParams | EChartFormatterParams[],
  config: DashboardAxisConfig,
  formatAmount: (value: unknown) => string,
) {
  const entries = Array.isArray(params) ? params : [params]
  return entries
    .map((entry, index) => {
      const xValue = config.swapXY ? entry?.value?.[1] : entry?.value?.[0]
      const yValue = config.swapXY ? entry?.value?.[0] : entry?.value?.[1]
      const category = formatDashboardTooltipCategory(xValue, config)
      const heading = index === 0 ? `<div>${category}</div>` : ''
      return `${heading}<div>${entry?.marker || ''}${entry?.seriesName || ''}: <strong>${formatAmount(yValue)}</strong></div>`
    })
    .join('')
}

function formatDashboardTooltipCategory(
  value: unknown,
  config: DashboardAxisConfig,
) {
  if (config.xAxis?.type === 'time' && value) {
    return dayjs(String(value)).format('MMMM D, YYYY')
  }
  return value ?? ''
}

function asChartValue(value: unknown): ChartValue {
  return typeof value === 'number' || typeof value === 'string' || value == null
    ? value
    : undefined
}

function getNumberPart(
  locale: string | undefined,
  value: number,
  type: Intl.NumberFormatPartTypes,
) {
  return new Intl.NumberFormat(locale)
    .formatToParts(value)
    .find((part) => part.type === type)?.value
}

function normalizeSpaces(value: string) {
  return value.replace(/[\u00a0\u202f]/g, ' ')
}

export function getLastXDays(
  range: number = 30,
  today: Date = new Date(),
): string {
  const lastXDate = new Date(today)
  lastXDate.setDate(today.getDate() - (range - 1))

  return `${dayjs(lastXDate).format('YYYY-MM-DD')},${dayjs(today).format(
    'YYYY-MM-DD',
  )}`
}

export function getDashboardDateRange(
  period: DashboardPeriod,
  customRange: string | null = null,
  today: Date = new Date(),
): string | null {
  if (period === 'Custom Range') return customRange
  if (period === 'Today') return getLastXDays(1, today)

  if (period === 'Yesterday') {
    const yesterday = new Date(today)
    yesterday.setDate(today.getDate() - 1)
    return getLastXDays(1, yesterday)
  }

  const ranges = {
    'Last 7 Days': 7,
    'Last 30 Days': 30,
    'Last 60 Days': 60,
    'Last 90 Days': 90,
  }
  return getLastXDays(ranges[period], today)
}

export function formatter(range: string) {
  const [from, to] = range.split(',')
  return `${formatRange(from)} to ${formatRange(to)}`
}

function parseDateOnly(date: string) {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function formatRange(date: string) {
  const dateObj = parseDateOnly(date)
  return dateObj.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year:
      dateObj.getFullYear() === new Date().getFullYear()
        ? undefined
        : 'numeric',
  })
}
