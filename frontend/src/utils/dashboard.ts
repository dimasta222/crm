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

export function isDashboardCurrencyCard(metricType: string | undefined) {
  return Boolean(metricType && PRINT_STUDIO_MONETARY_METRICS.has(metricType))
}

export function formatDashboardCurrency(
  value: number | string | null | undefined,
  symbol: string,
) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string' && !value.trim()) return '—'

  const precision = getCurrencyPrecision()
  const formatted =
    typeof value === 'string'
      ? formatDecimalString(value, precision)
      : formatFiniteNumber(value, precision)
  if (!formatted) return '—'

  return `${formatted}${symbol ? ` ${symbol}` : ''}`
}

export function getDashboardCurrencyValueClass(formatted: string) {
  if (formatted.length > 26) return 'text-sm'
  if (formatted.length > 18) return 'text-lg'
  return 'text-2xl'
}

function getCurrencyPrecision() {
  const rawPrecision =
    typeof window !== 'undefined'
      ? window.sysdefaults?.currency_precision
      : undefined
  if (
    rawPrecision === null ||
    rawPrecision === undefined ||
    rawPrecision === ''
  )
    return 2
  const configured = Number(rawPrecision)
  if (!Number.isInteger(configured)) return 2
  return Math.min(9, Math.max(0, configured))
}

function formatFiniteNumber(value: number, precision: number) {
  if (!Number.isFinite(value)) return null
  const fractionDigits = Number.isInteger(value) ? 0 : precision
  return normalizeSpaces(
    new Intl.NumberFormat(getCurrentLocale(), {
      notation: 'standard',
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
      useGrouping: true,
    }).format(value),
  )
}

function formatDecimalString(value: string, precision: number) {
  const match = value.trim().match(/^([+-]?)(\d+)(?:\.(\d+))?$/)
  if (!match) return null

  const [, sign, integer, fraction = ''] = match
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
  const integerFormatted = normalizeSpaces(
    new Intl.NumberFormat(locale, {
      maximumFractionDigits: 0,
      useGrouping: true,
    }).format(BigInt(integerText)),
  )
  const isZero = scaled === 0n
  const minus =
    sign === '-' && !isZero ? getNumberPart(locale, -1, 'minusSign') : ''
  const decimal = getNumberPart(locale, 1.1, 'decimal') || '.'
  const visibleFraction = fractionText && BigInt(fractionText) !== 0n
  return `${minus}${integerFormatted}${visibleFraction ? decimal + fractionText : ''}`
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
