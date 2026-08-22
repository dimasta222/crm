// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file, vue/require-prop-types */

import { createApp, defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createDocument: vi.fn(),
  fetchProduct: vi.fn(),
}))

vi.mock('@/composables/document', () => ({
  createDocument: mocks.createDocument,
}))

vi.mock('frappe-ui', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    Button: defineComponent({
      props: ['label', 'tooltip', 'disabled'],
      emits: ['click'],
      setup:
        (props, { emit }) =>
        () =>
          h(
            'button',
            {
              disabled: props.disabled,
              title: props.tooltip,
              onClick: () => emit('click'),
            },
            props.label || props.tooltip,
          ),
    }),
    Checkbox: defineComponent({
      props: ['modelValue', 'label'],
      emits: ['update:modelValue'],
      setup:
        (props, { emit }) =>
        () =>
          h('label', [
            h('input', {
              type: 'checkbox',
              checked: Boolean(props.modelValue),
              onChange: (event) =>
                emit('update:modelValue', event.target.checked),
            }),
            props.label,
          ]),
    }),
    FormControl: defineComponent({
      props: ['modelValue', 'placeholder', 'type'],
      emits: ['update:modelValue', 'input'],
      setup:
        (props, { emit }) =>
        () =>
          h('input', {
            type: props.type || 'text',
            value: props.modelValue,
            placeholder: props.placeholder,
            onInput: (event) => {
              emit('update:modelValue', event.target.value)
              emit('input', event)
            },
          }),
    }),
    Select: defineComponent({
      props: ['modelValue'],
      setup: (props) => () => h('span', props.modelValue),
    }),
    createResource: () => ({ fetch: mocks.fetchProduct }),
  }
})

vi.mock('@/components/Section.vue', () => ({
  default: defineComponent({
    props: ['label'],
    setup:
      (props, { slots }) =>
      () =>
        h('section', [props.label, slots.actions?.(), slots.default?.()]),
  }),
}))

vi.mock('@/components/Controls/Link.vue', () => ({
  default: defineComponent({
    props: ['modelValue', 'placeholder'],
    setup: (props) => () =>
      h('input', { value: props.modelValue, placeholder: props.placeholder }),
  }),
}))

vi.mock('@/stores/meta', async () => {
  const { ref } = await import('vue')
  return {
    getMeta: () => ({ doctypeMeta: ref({ fields: [] }) }),
  }
})

import DtfRollTable from '@/components/OrderEditor/DtfRollTable.vue'
import OrderApplicationsTable from '@/components/OrderEditor/OrderApplicationsTable.vue'
import OrderItemsTable from '@/components/OrderEditor/OrderItemsTable.vue'

let mountedApp

function mount(component, doc) {
  const container = document.createElement('div')
  document.body.append(container)
  mountedApp = createApp(component, { doc })
  mountedApp.config.globalProperties.__ = globalThis.__
  mountedApp.mount(container)
  return container
}

function button(container, label) {
  return [...container.querySelectorAll('button')].find(
    (candidate) => candidate.textContent === label,
  )
}

beforeAll(() => {
  globalThis.__ = (message) => message
  window.sysdefaults = { currency_precision: 2 }
})

afterEach(() => {
  mountedApp?.unmount()
  mountedApp = null
  document.body.replaceChildren()
  vi.restoreAllMocks()
  mocks.createDocument.mockReset()
  mocks.fetchProduct.mockReset()
})

describe('order editor stage 3.3B components', () => {
  it('renders optional print dimensions for every application row', () => {
    const container = mount(OrderApplicationsTable, {
      order_items: [{ item_key: 'ITEM-1', item_name: 'Футболка' }],
      order_applications: [
        {
          item_key: 'ITEM-1',
          production_type: 'DTF Printing',
          width_cm: 20,
          height_cm: 30,
        },
        {
          item_key: 'ITEM-1',
          production_type: 'Embroidery',
          width_cm: 8,
          height_cm: 5,
        },
      ],
    })

    expect(container.textContent).toContain('Width (cm)')
    expect(container.textContent).toContain('Height (cm)')
    const values = [...container.querySelectorAll('input')].map(
      (input) => input.value,
    )
    expect(values).toEqual(expect.arrayContaining(['20', '30', '8', '5']))
    expect(container.querySelector('[required]')).toBeNull()
  })

  it('renders calculated, manual final, and equivalent DTF values', () => {
    const container = mount(DtfRollTable, {
      currency: 'USD',
      dtf_roll_lines: [
        {
          length_m: 3,
          rate_per_meter: 500,
          manual_amount: 1400,
          use_manual_amount: 1,
        },
      ],
    })

    expect(
      container.querySelector('[data-testid="dtf-calculated-amount"]')
        .textContent,
    ).toContain('1,500.00')
    expect(
      container.querySelector('[data-testid="dtf-final-amount"]').textContent,
    ).toContain('1,400.00')
    expect(
      container.querySelector('[data-testid="dtf-equivalent-rate"]')
        .textContent,
    ).toContain('466.67')
  })

  it('applies a manual zero only through the explicit rate action', async () => {
    const row = {
      length_m: 2,
      rate_per_meter: 500,
      manual_amount: 0,
      use_manual_amount: 1,
    }
    const container = mount(DtfRollTable, {
      currency: 'USD',
      dtf_roll_lines: [row],
    })

    expect(row.rate_per_meter).toBe(500)
    expect(
      container.querySelector('[data-testid="dtf-final-amount"]').textContent,
    ).toContain('0.00')
    button(container, 'Apply as rate per meter').click()
    await nextTick()

    expect(row).toMatchObject({
      rate_per_meter: 0,
      use_manual_amount: 0,
      manual_amount: null,
    })
  })

  it('creates a product through the standard modal and loads its rate', async () => {
    const row = {
      item_key: 'ITEM-1',
      supply_type: 'Studio Product',
      product: '',
    }
    const container = mount(OrderItemsTable, {
      order_items: [row],
      order_applications: [],
    })
    mocks.fetchProduct.mockResolvedValue({ standard_rate: 1250 })

    button(container, 'Create product').click()
    expect(mocks.createDocument).toHaveBeenCalledWith(
      'CRM Product',
      {},
      null,
      expect.any(Function),
    )
    await mocks.createDocument.mock.calls[0][3]({ name: 'PRODUCT-001' })

    expect(row).toMatchObject({
      product: 'PRODUCT-001',
      base_rate: 1250,
    })
  })

  it('opens the selected product in a new tab', () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const container = mount(OrderItemsTable, {
      order_items: [
        {
          item_key: 'ITEM-1',
          supply_type: 'Studio Product',
          product: 'PRODUCT / 001',
        },
      ],
      order_applications: [],
    })

    button(container, 'Open product').click()
    expect(open).toHaveBeenCalledWith(
      '/app/crm-product/PRODUCT%20%2F%20001',
      '_blank',
      'noopener',
    )
  })

  it('shows creation and rate errors without substituting a zero rate', async () => {
    const row = {
      item_key: 'ITEM-1',
      supply_type: 'Studio Product',
      product: '',
      base_rate: 75,
    }
    const container = mount(OrderItemsTable, {
      order_items: [row],
      order_applications: [],
    })

    button(container, 'Create product').click()
    await mocks.createDocument.mock.calls[0][3](null)
    await nextTick()
    expect(container.textContent).toContain('Unable to create the product.')

    mocks.fetchProduct.mockRejectedValue(new Error('not permitted'))
    button(container, 'Create product').click()
    await mocks.createDocument.mock.calls[1][3]({ name: 'PRODUCT-002' })
    await nextTick()
    expect(container.textContent).toContain('Unable to load the product rate.')
    expect(row.base_rate).toBeNull()
    expect(row.base_rate).not.toBe(0)
  })

  it('does not expose catalog actions for Customer Items', () => {
    const container = mount(OrderItemsTable, {
      order_items: [{ item_key: 'ITEM-1', supply_type: 'Customer Item' }],
      order_applications: [],
    })

    expect(button(container, 'Create product')).toBeUndefined()
    expect(button(container, 'Open product')).toBeUndefined()
  })
})
