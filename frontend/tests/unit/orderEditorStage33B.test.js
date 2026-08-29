// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file, vue/require-prop-types */

import { createApp, defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createDocument: vi.fn(),
  fetchProduct: vi.fn(),
  showModal: vi.fn(),
}))

vi.mock('@/composables/document', () => ({
  createDocument: mocks.createDocument,
}))

vi.mock('@/composables/doctypeModal', () => ({
  useDoctypeModal: () => ({ showModal: mocks.showModal }),
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
      props: ['modelValue', 'label', 'placeholder', 'type'],
      emits: ['update:modelValue', 'input'],
      setup:
        (props, { emit }) =>
        () =>
          h('label', [
            props.label,
            h('input', {
              type: props.type || 'text',
              value: props.modelValue,
              placeholder: props.placeholder,
              onInput: (event) => {
                emit('update:modelValue', event.target.value)
                emit('input', event)
              },
            }),
          ]),
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
  mocks.showModal.mockReset()
})

describe('order editor stage 3.3B components', () => {
  it('renders optional print dimensions for every application row', async () => {
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

    const parametersButtons = [...container.querySelectorAll('button')].filter(
      (candidate) => candidate.textContent === 'Parameters',
    )
    for (const parametersButton of parametersButtons) {
      parametersButton.click()
    }
    await nextTick()

    expect(container.textContent).toContain('Width (cm)')
    expect(container.textContent).toContain('Height (cm)')
    const values = [...container.querySelectorAll('input')].map(
      (input) => input.value,
    )
    expect(values).toEqual(expect.arrayContaining(['20', '30', '8', '5']))
    expect(container.querySelector('[required]')).toBeNull()
  })

  it('shows compact embroidery parameters and an optional service comment', async () => {
    const container = mount(OrderApplicationsTable, {
      currency: 'RUB',
      order_items: [{ item_key: 'ITEM-1', item_name: 'Футболка' }],
      order_applications: [
        {
          item_key: 'ITEM-1',
          production_type: 'Embroidery',
          placement: 'Chest',
          qty: 32,
          stitch_count: 12500,
          stitch_rate_per_1000: 70,
          embroidery_setup_fee: 500,
          comment: 'На каждой футболке своё имя',
        },
      ],
    })

    button(container, 'Parameters').click()
    await nextTick()

    expect(container.textContent).toContain('Stitch count')
    expect(container.textContent).toContain('Rate per 1,000 stitches')
    expect(container.textContent).toContain('Embroidery artwork preparation')
    expect(container.textContent).toContain('Comment')
    expect(
      [...container.querySelectorAll('input')].map((input) => input.value),
    ).toEqual(
      expect.arrayContaining([
        '12500',
        '70',
        '500',
        'На каждой футболке своё имя',
      ]),
    )
    expect(container.querySelector('[required]')).toBeNull()
  })

  it('shows screen-printing colors and fabric without requiring dimensions', async () => {
    const container = mount(OrderApplicationsTable, {
      currency: 'RUB',
      order_items: [{ item_key: 'ITEM-1', item_name: 'Футболка' }],
      order_applications: [
        {
          item_key: 'ITEM-1',
          production_type: 'Screen Printing',
          placement: 'Chest',
          qty: 10,
          rate: 250,
          screen_color_count: 3,
          fabric_type: 'Dark',
        },
      ],
    })

    button(container, 'Parameters').click()
    await nextTick()

    expect(container.textContent).toContain('Number of colors')
    expect(container.textContent).toContain('Fabric type')
    expect(container.textContent).toContain('Dark')
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
    await nextTick()

    expect(row).toMatchObject({
      product: 'PRODUCT-001',
      base_rate: 1250,
      manual_rate: 1250,
      use_manual_rate: 1,
    })
  })

  it('opens the selected product in the CRM editor', () => {
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
    expect(mocks.showModal).toHaveBeenCalledWith({
      name: 'PRODUCT / 001',
      doctype: 'CRM Product',
      title: 'Product',
      callbacks: { afterUpdate: expect.any(Function) },
    })
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
    expect(container.textContent).toContain('Not charged')
  })
})
