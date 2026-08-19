import { dayjs } from 'frappe-ui'

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
