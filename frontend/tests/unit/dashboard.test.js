import {
  formatRange,
  getDashboardDateRange,
  getLastXDays,
  PRINT_STUDIO_AXIS_CHARTS,
  PRINT_STUDIO_DONUT_CHARTS,
  PRINT_STUDIO_NUMBER_CHARTS,
} from '@/utils/dashboard'

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
