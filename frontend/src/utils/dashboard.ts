import { dayjs } from 'frappe-ui'

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
