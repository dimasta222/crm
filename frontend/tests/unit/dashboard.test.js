import {
  formatRange,
  formatDashboardCurrency,
  getDashboardChartConfig,
  getDashboardCurrencyValueClass,
  getDashboardDateRange,
  getLastXDays,
  isDashboardCurrencyCard,
  PRINT_STUDIO_AXIS_CHARTS,
  PRINT_STUDIO_DONUT_CHARTS,
  PRINT_STUDIO_NUMBER_CHARTS,
} from '@/utils/dashboard'

vi.mock('frappe-ui', () => ({
  dayjs: (value) => ({
    format: (format) => {
      const date = value instanceof Date ? value : new Date(`${value}T00:00:00`)
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      if (format === 'MMMM D, YYYY') {
        const monthName = date.toLocaleString('en-US', { month: 'long' })
        return `${monthName} ${date.getDate()}, ${year}`
      }
      return `${year}-${month}-${day}`
    },
  }),
}))

describe('dashboard number card formatting', () => {
  const originalLanguage = document.documentElement.lang
  const originalSysdefaults = window.sysdefaults

  afterEach(() => {
    document.documentElement.lang = originalLanguage
    window.sysdefaults = originalSysdefaults
  })

  it('uses the current Russian application locale without compact notation', () => {
    document.documentElement.lang = 'ru-RU'
    expect(formatDashboardCurrency(0, '₽')).toBe('0 ₽')
    expect(formatDashboardCurrency('0', '₽')).toBe('0 ₽')
    expect(formatDashboardCurrency(1000, '₽')).toBe('1000 ₽')
    expect(formatDashboardCurrency(1500.5, '₽')).toBe('1500,50 ₽')
    expect(formatDashboardCurrency(-1500.5, '₽')).toBe('-1500,50 ₽')
    expect(formatDashboardCurrency('1500.50', '₽')).toBe('1500,50 ₽')
    expect(formatDashboardCurrency('1500.567', '₽')).toBe('1500,57 ₽')
    expect(formatDashboardCurrency(1000000, '₽')).toBe('1000000 ₽')
  })

  it.each([0, 2, 3])(
    'ignores system currency_precision=%s for dashboard money',
    (currencyPrecision) => {
      document.documentElement.lang = 'ru-RU'
      window.sysdefaults = { currency_precision: currencyPrecision }
      expect(formatDashboardCurrency(1000, '₽')).toBe('1000 ₽')
      expect(formatDashboardCurrency(1500.5, '₽')).toBe('1500,50 ₽')
      expect(formatDashboardCurrency('1500.50', '₽')).toBe('1500,50 ₽')
      expect(formatDashboardCurrency('1500.567', '₽')).toBe('1500,57 ₽')
    },
  )

  it('uses the current English application locale', () => {
    document.documentElement.lang = 'en-US'
    expect(formatDashboardCurrency(1000, '$')).toBe('1000 $')
    expect(formatDashboardCurrency('1500.50', '$')).toBe('1500.50 $')
  })

  it.each([null, undefined, '', '   ', 'invalid', NaN, Infinity, -Infinity])(
    'renders missing or invalid value %s as a neutral state',
    (value) => {
      expect(formatDashboardCurrency(value, '₽')).toBe('—')
    },
  )

  it('preserves every digit of a decimal string beyond Number.MAX_SAFE_INTEGER', () => {
    document.documentElement.lang = 'ru-RU'
    expect(formatDashboardCurrency('900719925474099312345.25', '₽')).toBe(
      '900719925474099312345,25 ₽',
    )

    document.documentElement.lang = 'en-US'
    expect(formatDashboardCurrency('900719925474099312345.25', '$')).toBe(
      '900719925474099312345.25 $',
    )
  })

  it('never adds compact notation or duplicates the dynamic symbol', () => {
    document.documentElement.lang = 'ru-RU'
    const result = formatDashboardCurrency('1500.50', '€')
    expect(result).not.toMatch(/[KMКМ]|тыс\.|млн/i)
    expect(result.match(/€/g)).toHaveLength(1)
  })

  it('uses adaptive classes only for long formatted values', () => {
    expect(getDashboardCurrencyValueClass('1500,50 ₽')).toBe('text-2xl')
    expect(getDashboardCurrencyValueClass('123456789012,34 ₽')).toBe('text-2xl')
    expect(getDashboardCurrencyValueClass('900719925474099312345,25 ₽')).toBe(
      'text-sm',
    )
  })

  it('identifies only the four explicit print studio monetary metrics', () => {
    expect(isDashboardCurrencyCard('total_order_amount')).toBe(true)
    expect(isDashboardCurrencyCard('paid_for_period_orders')).toBe(true)
    expect(isDashboardCurrencyCard('awaiting_payment')).toBe(true)
    expect(isDashboardCurrencyCard('average_order_value')).toBe(true)
    expect(isDashboardCurrencyCard('current_orders')).toBe(false)
    expect(isDashboardCurrencyCard('legacy_custom_card')).toBe(false)
  })
})

describe('dashboard monetary axis formatting', () => {
  it('disables compact and grouped values on axes, labels, and tooltips', () => {
    document.documentElement.lang = 'ru-RU'
    const original = {
      title: 'Amount by day',
      data: [{ date: '2026-08-20', amount: '1500.50' }],
      xAxis: { key: 'date', type: 'time' },
      yAxis: { title: 'Amount (₽)' },
      series: [{ name: 'amount', type: 'line' }],
    }
    const config = getDashboardChartConfig({
      name: 'completed_order_amount_by_day',
      type: 'axis_chart',
      data: original,
    })

    expect(config.yAxis.echartOptions.axisLabel.formatter(1000000)).toBe(
      '1000000',
    )
    expect(
      config.series[0].echartOptions.label.formatter({
        value: ['2026-08-20', '1500.50'],
      }),
    ).toBe('1500,50')
    const tooltip = config.echartOptions.tooltip.formatter([
      {
        value: ['2026-08-20', '1500.50'],
        seriesName: 'amount',
      },
    ])
    expect(tooltip).toContain('1500,50')
    expect(tooltip).toContain('August 20, 2026')
    expect(tooltip).not.toMatch(/\d(?:K|M)|тыс\.|млн|1\s500/i)
    expect(original.yAxis).not.toHaveProperty('echartOptions')
  })

  it('leaves count and legacy chart configs untouched', () => {
    const data = { yAxis: {}, series: [] }
    expect(
      getDashboardChartConfig({
        name: 'orders_by_production_type',
        type: 'axis_chart',
        data,
      }),
    ).toBe(data)
  })
})

const controlDate = new Date(2026, 7, 19, 12)

describe('dashboard date ranges', () => {
  it('returns today', () => {
    expect(getDashboardDateRange('Today', null, controlDate)).toBe(
      '2026-08-19,2026-08-19',
    )
  })

  it('returns yesterday', () => {
    expect(getDashboardDateRange('Yesterday', null, controlDate)).toBe(
      '2026-08-18,2026-08-18',
    )
  })

  it.each([
    ['Last 7 Days', '2026-08-13,2026-08-19'],
    ['Last 30 Days', '2026-07-21,2026-08-19'],
    ['Last 60 Days', '2026-06-21,2026-08-19'],
    ['Last 90 Days', '2026-05-22,2026-08-19'],
  ])('returns the inclusive range for %s', (period, expected) => {
    expect(getDashboardDateRange(period, null, controlDate)).toBe(expected)
  })

  it('handles a month boundary', () => {
    expect(getLastXDays(7, new Date(2026, 2, 3, 12))).toBe(
      '2026-02-25,2026-03-03',
    )
  })

  it('handles a year boundary', () => {
    expect(getLastXDays(7, new Date(2026, 0, 3, 12))).toBe(
      '2025-12-28,2026-01-03',
    )
  })

  it('preserves a custom range', () => {
    expect(
      getDashboardDateRange(
        'Custom Range',
        '2026-04-10,2026-05-02',
        controlDate,
      ),
    ).toBe('2026-04-10,2026-05-02')
  })

  it('formats date-only values without a negative timezone shift', () => {
    const originalTimezone = process.env.TZ
    process.env.TZ = 'America/Los_Angeles'

    try {
      expect(new Date('2026-04-10').getDate()).toBe(9)
      expect(formatRange('2026-04-10')).toMatch(/^Apr 10(?:, 2026)?$/)
    } finally {
      if (originalTimezone === undefined) {
        delete process.env.TZ
      } else {
        process.env.TZ = originalTimezone
      }
    }
  })
})

describe('print studio dashboard cards', () => {
  it('exposes all primary number cards to the chart picker', () => {
    expect(PRINT_STUDIO_NUMBER_CHARTS).toEqual([
      { label: 'Total order amount', value: 'total_order_amount' },
      { label: 'Paid for period orders', value: 'paid_for_period_orders' },
      { label: 'Awaiting Payment', value: 'awaiting_payment' },
      { label: 'Current orders (now)', value: 'current_orders' },
      { label: 'Completed orders', value: 'completed_orders' },
      { label: 'Average order value', value: 'average_order_value' },
      {
        label: 'Orders in production (now)',
        value: 'orders_in_production',
      },
      {
        label: 'Ready for pickup (now)',
        value: 'orders_ready_for_pickup',
      },
      { label: 'Overdue orders (now)', value: 'overdue_orders' },
      { label: 'Unpaid orders (now)', value: 'unpaid_orders' },
    ])
  })

  it('exposes only the current print studio graphs to the chart picker', () => {
    expect(PRINT_STUDIO_AXIS_CHARTS).toEqual([
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
    ])
    expect(PRINT_STUDIO_DONUT_CHARTS).toEqual([
      {
        label: 'Current statuses of period orders',
        value: 'orders_by_status',
      },
      { label: 'Orders by source', value: 'orders_by_source' },
    ])
  })
})
