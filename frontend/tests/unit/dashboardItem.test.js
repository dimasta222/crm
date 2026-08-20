import { createApp, h } from 'vue'
import DashboardItem from '@/components/Dashboard/DashboardItem.vue'

vi.mock('frappe-ui', async () => {
  const { defineComponent, h } = await import('vue')
  const { default: NumberChart } =
    await import('../../node_modules/frappe-ui/src/components/Charts/NumberChart.vue')
  const passthrough = defineComponent({
    setup(_, { slots }) {
      return () => h('div', slots.default?.())
    },
  })
  return {
    dayjs: () => ({ format: () => '' }),
    AxisChart: passthrough,
    DonutChart: passthrough,
    Tooltip: passthrough,
    NumberChart,
  }
})

function renderDashboardItem(item) {
  const container = document.createElement('div')
  document.body.append(container)
  const app = createApp({
    render: () => h(DashboardItem, { index: 0, item }),
  })
  app.config.globalProperties.__ = globalThis.__
  app.mount(container)
  return {
    container,
    unmount() {
      app.unmount()
      container.remove()
    },
  }
}

function deltaElement(container) {
  return container.querySelector('.text-xs.font-medium')
}

describe('DashboardItem number card rendering', () => {
  const originalLanguage = document.documentElement.lang

  afterEach(() => {
    document.documentElement.lang = originalLanguage
    document.body.innerHTML = ''
  })

  it('renders an order count through the actual NumberChart', () => {
    const view = renderDashboardItem({
      name: 'current_orders',
      type: 'number_chart',
      data: { title: 'Current orders', value: 12 },
    })
    expect(view.container.textContent).toContain('Current orders')
    expect(view.container.textContent).toContain('12')
    expect(
      view.container.querySelector('[data-testid="dashboard-currency-value"]'),
    ).toBeNull()
    expect(view.container.querySelector('.max-h-\\[140px\\]')).not.toBeNull()
    view.unmount()
  })

  it('keeps a legacy or custom prefix card on the actual NumberChart', () => {
    const view = renderDashboardItem({
      name: 'legacy_custom_card',
      type: 'number_chart',
      data: {
        title: 'Legacy sales',
        value: 1000,
        prefix: '€',
        delta: 7,
        deltaSuffix: '%',
      },
    })
    expect(view.container.textContent).toContain('Legacy sales')
    expect(view.container.textContent).toContain('1K')
    expect(view.container.textContent).toContain('€')
    expect(
      view.container.querySelector('[data-testid="dashboard-currency-value"]'),
    ).toBeNull()
    view.unmount()
  })

  it.each([
    [0, '0 ₽'],
    ['0', '0 ₽'],
    [1000, '1000 ₽'],
    [1500.5, '1500,50 ₽'],
    [-1500.5, '-1500,50 ₽'],
    ['1500.50', '1500,50 ₽'],
    [1000000, '1000000 ₽'],
    [null, '—'],
    [undefined, '—'],
    ['', '—'],
    ['invalid', '—'],
  ])('renders monetary value %s in full', (input, expected) => {
    document.documentElement.lang = 'ru-RU'
    const view = renderDashboardItem({
      name: 'total_order_amount',
      type: 'number_chart',
      data: {
        title: 'Total order amount',
        value: input,
        prefix: '₽',
      },
    })
    const value = view.container.querySelector(
      '[data-testid="dashboard-currency-value"]',
    )
    expect(value.textContent.trim()).toBe(expected)
    expect(value.title).toBe(expected)
    expect(value.className).toContain('overflow-auto')
    expect(value.textContent).not.toMatch(/[KMКМ]|тыс\.|млн/i)
    expect(value.textContent.match(/₽/g)?.length || 0).toBe(
      expected === '—' ? 0 : 1,
    )
    view.unmount()
  })

  it('shrinks a long value while keeping its complete title and text', () => {
    document.documentElement.lang = 'en-US'
    const expected = '900719925474099312345.25 $'
    const view = renderDashboardItem({
      name: 'total_order_amount',
      type: 'number_chart',
      data: {
        title: 'Total order amount',
        value: '900719925474099312345.25',
        prefix: '$',
      },
    })
    const value = view.container.querySelector(
      '[data-testid="dashboard-currency-value"]',
    )
    expect(value.textContent.trim()).toBe(expected)
    expect(value.title).toBe(expected)
    expect(value.className).toContain('text-sm')
    expect(value.className).toContain('max-w-full')
    expect(value.className).toContain('break-all')
    view.unmount()
  })
})

describe('DashboardItem matches the pinned NumberChart delta contract', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  function renderDelta(delta, negativeIsBetter = false, extra = {}) {
    return renderDashboardItem({
      name: 'total_order_amount',
      type: 'number_chart',
      data: {
        title: 'Total order amount',
        value: 1000,
        prefix: '$',
        delta,
        negativeIsBetter,
        ...extra,
      },
    })
  }

  it('renders a positive delta green when negativeIsBetter is false', () => {
    const view = renderDelta(12.5, false, {
      deltaPrefix: '$',
      deltaSuffix: '% MoM',
    })
    const delta = deltaElement(view.container)
    expect(delta.textContent.replace(/\s+/g, '')).toBe('↑$12.5%MoM')
    expect(delta.className).toContain('text-ink-green-3')
    view.unmount()
  })

  it('renders a negative delta red when negativeIsBetter is false', () => {
    const view = renderDelta(-2, false, { deltaSuffix: ' days' })
    const delta = deltaElement(view.container)
    expect(delta.textContent.replace(/\s+/g, '')).toBe('↓-2days')
    expect(delta.className).toContain('text-ink-red-4')
    view.unmount()
  })

  it('renders a positive delta red when negativeIsBetter is true', () => {
    const view = renderDelta(2, true)
    expect(deltaElement(view.container).className).toContain('text-ink-red-4')
    view.unmount()
  })

  it('renders a negative delta green when negativeIsBetter is true', () => {
    const view = renderDelta(-2, true)
    expect(deltaElement(view.container).className).toContain('text-ink-green-3')
    view.unmount()
  })

  it('does not render a delta row for zero or an absent delta', () => {
    const zero = renderDelta(0)
    expect(deltaElement(zero.container)).toBeNull()
    expect(zero.container.querySelector('.pb-3')).not.toBeNull()
    zero.unmount()

    const absent = renderDelta(undefined)
    expect(deltaElement(absent.container)).toBeNull()
    expect(absent.container.querySelector('.pb-3')).not.toBeNull()
    absent.unmount()
  })
})
